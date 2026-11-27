# Connecting the one-button poster

`stylebrain publish` posts a prepared reel to Instagram, TikTok, YouTube
Shorts and Facebook Reels through each app's official API. Every app is free to use this way, but
each one needs a one-time "developer app" that belongs to you. Do this once per
account on the computer that will post. The sign-in files land in
`library/accounts/`, which is never committed.

Checked 2026-11-27. These consoles change their menus often, so names may
differ a little.

## YouTube Shorts (about 10 minutes)

1. Go to console.cloud.google.com and create a project, for example
   "Michael poster".
2. Under APIs & Services, Library, turn on **YouTube Data API v3**.
3. Under Google Auth Platform (OAuth consent screen), choose **External**, fill
   in the app name and your email, and add the scope `youtube.upload`.
4. Set the publishing status to **In production**. While it says "Testing",
   Google signs you out every 7 days. It stays unverified, which is fine for
   your own channel: you click past one warning screen when you sign in.
5. Under Clients, create an OAuth client of type **Desktop app**, and download
   its JSON file.
6. Run `uv run stylebrain connect youtube --client path/to/client_secret.json`,
   sign in with the Google account that owns the channel, and allow uploads.

Videos post as public. Vertical and 3 minutes or less makes them Shorts.

## Instagram and Facebook Reels (about 15 minutes, one sign-in for both)

You need an Instagram **professional** account (creator or business), linked to
a **Facebook Page**. In the Instagram app: Settings, Account type and tools,
Switch to professional account; then link a Page under Accounts Center.

1. Go to developers.facebook.com, My Apps, Create app, type **Business**.
2. Add the product **Instagram** (Instagram API with Facebook Login for
   Business).
3. In Graph API Explorer, pick your app, and request a User token with
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `pages_manage_posts` and `business_management`. Sign in and allow them
   for your Page and your Instagram account.
4. From App settings, Basic, copy the App ID and App Secret.
5. Run `uv run stylebrain connect instagram --token USER_TOKEN --app-id ID --app-secret SECRET`.

The app can stay in development mode: you are its admin, so it can post to
your own account. Instagram allows about 50 API posts a day.

Facebook Reels go to the Page linked to Instagram, with the same sign-in.
Facebook's API only takes reels of 3 to 90 seconds; a longer reel is skipped
for Facebook and still posts everywhere else.

## TikTok (about 15 minutes, then a review)

1. Go to developers.tiktok.com, Manage apps, Connect an app.
2. Add **Login Kit** (platform: Desktop, redirect URI
   `http://localhost:8766/callback/`) and **Content Posting API** with
   **Direct Post** turned on. Scopes: `user.info.basic`, `video.publish`.
3. Copy the Client key and Client secret.
4. Run `uv run stylebrain connect tiktok --key KEY --secret SECRET`.

Until TikTok audits the app, every post goes up **private** ("only me"). Open
it in the TikTok app and set it to everyone. To lift that, submit the app for
review in the developer portal. TikTok may turn down a personal tool; if it
does, TikTok stays a one-tap step in the app. Once it passes, run
`connect tiktok` again with `--audited`.

## Posting

```
uv run stylebrain crosspost POST                 # prepare, then read and edit the .txt files
uv run stylebrain publish POST --dry-run         # check everything, send nothing
uv run stylebrain publish POST                   # post to all four
uv run stylebrain publish today                  # today's approved reel
uv run stylebrain publish-shortcut "%USERPROFILE%\Desktop"   # the double-click button
```

A platform with a problem (an unfilled `[weight]`, a caption over the limit, a
video too long) is skipped and the others still post. A platform that already
has a link for that post is never posted twice.
