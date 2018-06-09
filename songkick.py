#!/usr/bin/python
from requests import session
from bs4 import BeautifulSoup as bs

loginurl = 'https://accounts.songkick.com/session'
homeurl = 'https://www.songkick.com/tracker/artists'
tasteurl = 'https://www.songkick.com/taste_imports/lastfm'

def get_auth_tokens(soup):
    tags = soup.find_all(attrs={'name': 'authenticity_token'})
    return [tag['value'] for tag in tags]

def login(user, password):
    with session() as sess:
        formpage = bs(sess.get(loginurl + '/new').text, 'html5lib')
        token = get_auth_tokens(formpage)[0]
        resp = sess.post(loginurl, data={'username_or_email': user,
                                         'password': password,
                                         'authenticity_token': token})
        if resp.status_code == 200:
            return {'auth_http_s': sess.cookies['auth_http_s']}
        else:
            raise Exception('could not log in')

def hitme(lastfm_user, cookies):
    with session() as sess:
        page = bs(sess.get(homeurl, cookies=cookies).text, 'html5lib')
        form = page.find_all('form', attrs={'class': 'lastfm taste-import'})[0]
        token = get_auth_tokens(form)[0]
        resp = sess.post(tasteurl,
                         cookies=cookies,
                         data={'source_id': lastfm_user,
                               'authenticity_token': token})
        if resp.status_code != 200:
            raise Exception('could not import')

if __name__ == '__main__':
    from argparse import ArgumentParser
    from json import load, dump
    from getpass import getpass
    ap = ArgumentParser()
    ap.add_argument('--lastfm', default=None,
                    help='last.fm user name from which to import artists')
    ap.add_argument('--songkick', default=None,
                    help='songkick.com user (not required if using --cookie_json)')
    ap.add_argument('--cookie_json', default=None,
                    help='json file with auth secrets from an earlier --save_auth')
    ap.add_argument('--save_auth', default=None,
                    help='file to save auth secrets for later re-use')
    args = ap.parse_args()

    if args.lastfm is None and args.songkick is None:
        print 'must provide at least one account to work on'
        exit(-1)

    if args.cookie_json is None:
        user = args.songkick or input('songkick username or email address')
        password = getpass()
        auth = login(user, password)
    else:
        with open(args.cookie_json) as cookiefile:
            auth = load(cookiefile)

    if args.save_auth:
        with open(args.save_auth, 'w') as outfile:
            dump(auth, outfile)

    if args.lastfm:
        hitme(args.lastfm, auth)
