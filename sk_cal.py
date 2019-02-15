#!/usr/bin/python

import argparse
import base64
import httplib2
import json
import os
import string

from apiclient import discovery
from bs4 import BeautifulSoup as BS, Comment
from datetime import datetime as dt, timedelta
from oauth2client import client, tools
from oauth2client.file import Storage
from urllib2 import urlopen

SCOPES = ('https://www.googleapis.com/auth/gmail.readonly '
          + 'https://www.googleapis.com/auth/calendar')
CLIENT_SECRET_FILE = 'client_secret.json'
STATE = 'sk_state.json'

# comments that we track inside event blocks
DATE = ' Event Date '
HEADLINER = ' Event Headliner '
VENUE = ' Event Venue '
BUT_TIX = ' But Tickets Button ' # lol typos are forever
BUY_TIX = ' Buy Tickets Button ' # oh they fixed the typo?
DETAILS = ' Event Details Button '
TAGS = [DATE, HEADLINER, VENUE, BUT_TIX, BUY_TIX, DETAILS]

state = {'latest_checked': ''}


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    credential_file = 'sk_cal_credentials.json'

    store = Storage(credential_file)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = 'sk_cal'
        credentials = tools.run_flow(flow, store)
    return credentials


def get_events(service, q):
    # return all the events in emails found by query `q`
    global state # tracking most-recently-seen email
    events = []
    msgs = service.list(userId='me', q=q).execute()['messages']

    for msg in msgs:
        if msg['id'] == state['latest_checked']:
            break
        email = service.get(userId='me', id=msg['id']).execute()
        msg_events = parse_email(email)['events']
        for event in msg_events:
            # for debugging usage later
            event['source_msg_id'] = msg['id']
        events.extend(msg_events)

    state['latest_checked'] = msgs[0]['id']
    return events


def parse_email(email):
    #  parse the events (date, artists, venue, ticket purchase link) out of
    # an email
    bodytxt = str(email['payload']['parts'][1]['body']['data'])
    bodytxt = bodytxt.translate(string.maketrans('-_', '+/'))
    body = BS(base64.b64decode(bodytxt), 'html.parser')
    #  the html is messy, but the most straightforward scraping that I've worked
    # out is based on comment tags.
    comments = body.find_all(string=lambda s: (isinstance(s, Comment)
                                               and s.title() in TAGS))
    events = []
    for comment in comments:
        if comment.title() == DATE:
            events.append({'date': comment.findNext('td').text.strip()})
        elif comment.title() == HEADLINER:
            events[-1]['artists'] = comment.findNext('div').text.strip()
        elif comment.title() == VENUE:
            events[-1]['venue'] = comment.findNext('div').text.strip()
        elif comment.title() in (BUY_TIX, BUT_TIX, DETAILS):
            events[-1]['link'] = comment.findNext('a')['href']
    return {'events': events, 'soup': body}


def get_calid(service, name):
    # from a calendar name, get the google id for it
    calendars = service.calendarList().list().execute()
    ids = [item['id'] for item in calendars['items']
           if item['summary'] == name]
    if len(ids) == 0:
        return None
    if len(ids) == 1:
        return ids[0]
    return ids


def clear_cal(service, name):
    # delete all the events in a calendar
    clear_id = get_calid(service, name)

    # For some reason this doesn't work.
    #calserv.calendars().clear(calendarId=clear_id).execute()

    tok = None
    while True:
        entries = service.events().list(calendarId=clear_id,
                                        pageToken=tok).execute()
        for entry in entries['items']:
            service.events().delete(calendarId=clear_id,
                                    eventId=entry['id']).execute()
        tok = entries.get('nextPageToken')
        if not tok:
            break


def get_services():
    # get the gmail and calendar service objects
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    return {'gmail': discovery.build('gmail', 'v1', http=http),
            'calendar': discovery.build('calendar', 'v3', http=http)}


def try_sk_tickets(url):
    # try to follow "buy tickets" links to give a direct link on the calendar

    #  This will not strip out any tracking info, referer link, or whatever.
    # That behaviour is by design. Songkick is providing value to me, I want
    # them to be rewarded for that.
    try:
        soup = BS(urlopen(url).read(), 'html.parser')
    except Exception as e:
        return 'Error: %s'.format(e.message), 'http://'
    div = soup.find('div', id='tickets')
    if div and div.find('a') and 'href' in div.find('a'):
        return 'Buy Tickets', div.find('a')['href']
    else:
        # well at least give them the Songkick page.
        return 'No ticket info. Songkick Page', url

def main(args):
    global state
    if os.path.exists(STATE):
        with open(STATE) as statefile:
            state = json.load(statefile)

    services = get_services()
    msgserv, calserv = services['gmail'], services['calendar']
    calid = get_calid(calserv, args.update_cal)

    if args.clear_cal:
        clear_cal(calserv, args.clear_cal)

    for event in get_events(msgserv.users().messages(), args.gmail_search):
        print u'{date}: {artists} at {venue}'.format(**event)
        if args.update_cal:
            def todate(s):
                return dt.strptime(s.strip().split(' ', 1)[1], '%d %B %Y')
            when = event['date'].split(u'\u2013')
            when[0] = todate(when[0])
            if len(when) == 1:
                # one-day event (this is the norm)
                # can't have a calendar event span 0 days
                when.append(when[0] + timedelta(1))
            else:
                # multi-day event with start/end seperated by \u2013
                # also need to add a day so that the event spans properly
                when[1] = todate(when[1]) + timedelta(1)
            start = when[0].strftime('%Y-%m-%d')
            end = when[1].strftime('%Y-%m-%d')
            txt, link = try_sk_tickets(event['link'])
            if link.startswith('/'):
                link = 'https://www.songkick.com' + link
            cal_event = {'summary': event['artists'],
                         'location': event['venue'],
                         'start': {'date': start},
                         'end': {'date': end},
                         'description': '<a href="{}">{}</a>'.format(link, txt)
                        }
            calserv.events().insert(calendarId=calid, body=cal_event).execute()

    if not args.no_save_state:
        with open(STATE, 'w') as statefile:
            json.dump(state, statefile)


if __name__ == '__main__':
    #  this doesn't seem to help. If we need to do the OAuth dance, it'll still
    # complain about not recognizing our own args. To fix this, just run once
    # with no args to get the credentials, then use as normal after that.
    ap = argparse.ArgumentParser(parents=[tools.argparser])
    ap.add_argument('--no-save-state', action='store_true',
                    help='do not update state for next run')
    ap.add_argument('--update-cal', help='calendar name to update',
                    default='skstate')
    ap.add_argument('--clear-cal',
                    help='calendar name to clear out (before any update)')
    ap.add_argument('--gmail-search', default='label:songkick',
                    help='search string to use to find emails from Songkick')
    args = ap.parse_args()

    main(args)
