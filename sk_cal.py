#!/usr/bin/python

import argparse
import base64
import httplib2
import json
import os
import string

from apiclient import discovery
from bs4 import BeautifulSoup as BS
from bs4 import Comment
from datetime import datetime as dt, timedelta
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from urllib2 import urlopen

SCOPES = ('https://www.googleapis.com/auth/gmail.readonly '
          + 'https://www.googleapis.com/auth/calendar')
CLIENT_SECRET_FILE = 'client_secret.json'
STATE = 'sk_state.json'
DATE = ' Event Date '
HEADLINER = ' Event Headliner '
VENUE = ' Event Venue '
BUY_TIX = ' But Tickets Button ' # lol typos are forever
TAGS = [DATE, HEADLINER, VENUE, BUY_TIX]
translator = string.maketrans('-_', '+/')
state = {'latest_checked': ''}

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'gmail-python.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = 'skstate'
        credentials = tools.run_flow(flow, store)
    return credentials


def get_events(service, q):
    global state
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
    bodytxt = str(email['payload']['parts'][1]['body']['data'])
    body = BS(base64.b64decode(bodytxt.translate(translator)),
              'html.parser')
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
        elif comment.title() == BUY_TIX:
            events[-1]['link'] = comment.findNext('a')['href']
    return {'events': events, 'soup': body}

def get_calid(service, name):
    calendars = service.calendarList().list().execute()
    ids = [item['id'] for item in calendars['items']
           if item['summary'] == name]
    if len(ids) == 0:
        return None
    if len(ids) == 1:
        return ids[0]
    return ids

def clear_cal(service, name):
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
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    return {'gmail': discovery.build('gmail', 'v1', http=http),
            'calendar': discovery.build('calendar', 'v3', http=http)}

def try_sk_tickets(url):
    try:
        soup = BS(urlopen(url).read(), 'html.parser')
    except Exception as e:
        return 'Error: %s'.format(e.message), 'http://'
    div = soup.find('div', id='tickets')
    if div is not None:
        return 'Buy Tickets', div.find('a')['href']
    else:
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

    
    for event in get_events(msgserv.users().messages(), 'label:songkick'):
        print u'{date}: {artists} at {venue}'.format(**event)
        if args.update_cal:
            def todate(s):
                return dt.strptime(s.strip().split(' ', 1)[1], '%d %B %Y')
            when = event['date'].split(u'\u2013')
            when[0] = todate(when[0])
            if len(when) == 1:
                # one-day event (this is the norm)
                when.append(when[0] + timedelta(1))
            else:
                # multi-day event with start/end seperated by \u2013
                when[1] = todate(when[1])
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-save-state', action='store_true',
                    help='do not update state for next run')
    ap.add_argument('--update-cal', help='calendar name to update',
                    default='skstate')
    ap.add_argument('--clear-cal',
                    help='calendar name to clear out (before any update)')
    args = ap.parse_args()

    main(args)
