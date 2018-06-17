# Live Music Tracker

I *really* like going to see live music; it's basically my favourite kind of outing. San Francisco and Oakland are amazing for getting out to see shows, if you know they're happening. Here's how I know when they're happening.

My system starts with [Spotify](https://www.spotify.com/) (I have no relation with any services mentioned here), where most of my music listening happens. Given that I tend to build my own playlists, it's a very good bet that if I've listened to an artist on Spotify, I'm interested in seeing them live. To keep track of bands I listen to, I start by "scrobbling" my Spotify listens to [Last.fm](https://last.fm), and conveniently Songkick can import all the bands there (at the time I started this, Songkick had no integration with Spotify, and Spotify had no concerts integration at all).

Unfortunately, as best I can tell there's no way to have Songkick "follow" a Last.fm user, just a one-time import, and logging in to update with any regularity as I discover more artists is annoying. Python to the rescue! I have a crontab entry running `songkick.py` to import my artist list every night, and I've basically stopped worrying about not hearing about a show I want to see. Even more, I've developed a habit now of adding artists to my "currently playing" playlist on Spotify when I first hear them if I want to keep track, and soon afterwards they'll get played and slurped into my concert tracking setup.

`songkick.py` itself is just enough pattern matching (thanks [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)!) to be able to log in to Songkick and do an artist import.

## Calendar Integration

Not satisfied with just getting notifications for upcoming shows (which get shuffled off to their own label in my email), I figured I could automate another couple steps. Dusting off the [Gmail](https://developers.google.com/gmail/api/) and [Google Calendar](https://developers.google.com/calendar/) APIs, I then wrote sk_cal.py to go through all of the emails Songkick sends me and create events on a calendar I created for the purpose, noting the band and location of the event, and adding a link to buy the tickets.

> A sidenote on business models.
> I assume Songkick makes their money in two ways: a little bit by running ads on their site (because who doesn't?) but I would guess mostly by collecting referral fees for tickets bought through concert notifications from their site. I suspect one could dig a little bit harder and create "Buy Tickets" links that cut out the tracking info that allows them to collect their referral fee for the purchase, but I will not do so. I think it's important that they be able to make money on the value they provide me, and would like them to be able to continue to do so. With that mindset, I would even go out of my way to go through their system to buy tickets when I can.
> I encourage you to also try to create things that provide value and pay others when they add value for you.

Now, with that integration running nightly, I can either buy tickets straight from the notifications that are emailed to me, or from events if/when I see them come up on my calendar. Furthermore, when I'm looking ahead to check plans, I can see when concerts are coming up, even if I haven't checked my Songkick notifications or I've forgotten a concert I haven't bought tickets for yet.

## Further Work

Unfortunately, all of the data munging is done through HTML scraping, so it's rather brittle. The email scraping has already had to change once, and feels particularly fragile given how mangled the markup is. It's definitely worth keeping an eye on the services used to see if I should integrate with some first-class APIs instead.

Even more than that, this "workflow" relies on three (four if you count Google) services that I don't have control over. I'm not fundamentally against that, but it's not lost on me that any of them could disappear with no notice or recourse. It would be good to be able to backup data I'm storing on them, at least the list of artists as it is scrobbled to Last.fm. It would be fairly annoying to no longer get notifications for concerts, but especially so to lose the list of interesting artists that I've built up.

If I got really ambitious, I would rename the "Buy Tickets" link to "Learn More", and then create a script to work out ticket availability and price, and give me a "One-Click Buy" button to further streamline the purchasing process. I get lazy and often plan to buy tickets "later", but I guess I'm not too lazy to create systems to work around my laziness.
