# Instagram Trial Reels: what the research says (Nov 2026)

How the editor's five-version trial set (`stylebrain trial-*`, `src/stylebrain/trials.py`) was
designed, and what each choice rests on. "Official" means Instagram or Meta said it; the rest is
creators' and tool makers' experience, worth testing rather than trusting.

## How trials work (official)

- A trial reel is shown to **non-followers first**. Followers do not see it in Feed or the Reels
  tab, and it is not on the profile grid unless shared. Followers can still meet it through a DM
  share or an audio, location or filter page. ([Instagram Creators blog][ig])
- **Insights arrive about 24 hours** after posting: views, likes, comments, shares (Buffer also
  lists skip rate, saves, accounts reached and average watch time). ([Instagram][ig], [Buffer][buffer])
- **Graduation**: share to everyone by hand, or turn on automatic sharing, judged on the views in
  the **first 72 hours**. The threshold is not published, and the automatic setting carries over to
  later trials. ([Instagram][ig], [AdaptlyPost quoting the Help Center][adaptly])
- **Duplicates**: the Help Center warns, "Your trial reel may get limited reach if Instagram detects
  that you've previously shared the same content." ([quoted by FavStash][favstash] and [AdaptlyPost][adaptly])
- Mosseri: trials "get less reach, almost always", so compare trials with trials, not with normal
  reels. ([quoted by Buffer][buffer])
- **API**: since December 2025 the Content Publishing API can create trial reels: `trial_params`
  with `graduation_strategy` `MANUAL` or `SS_PERFORMANCE` on the `/media` container. ([Meta developer
  blog][meta], [Content Publishing docs][metadocs]) `stylebrain trial-publish` uses `MANUAL`.
- Eligibility: a public professional account (sources say 200 followers; one says 1,000). Trials
  cannot have Collab partners (Buffer).

## What creators do (experience, not rules)

- **One variable per test**, everything else identical (caption, hashtags, location). ([Buffer][buffer])
  The editor refuses a version that changes two things.
- **Which variable**: hooks first, almost everyone agrees. Text-only and music-only changes were the
  ones creators most often saw flagged as duplicates; a new spoken line plus a new first shot did best.
  ([FavStash][favstash]) So the default set leans on opening and hook changes, and a caption-only
  version is allowed but warned about.
- **How many**: Buffer's author runs 2 or 3 hook variants per reel; FavStash suggests 3 with spares;
  Mindwand 5 to 10. Five (Michael's ask) is at the high end, so `trial-learn` watches for a
  duplicate penalty: if versions posted later keep doing worse, post fewer or change more.
- **Spacing**: one a day at the same hour (FavStash, ViralSlice). `trial-schedule` defaults to 24 hours.
- **Volume**: no published cap; creators report about 5 trials a day is safe and one lost the
  feature for a day after 25. ([FavStash][favstash]) `trial-schedule` warns past 5 a day. With 7
  reels a week that is exactly 35 trials a week: the cap is reached, so spread start days.
- **Reading results**: skip rate first, then average watch time, then shares and saves (Buffer,
  FavStash). Thresholds like "45% completion" or "within 20%" are single-blog rules of thumb; the
  editor uses a two-proportion test instead, and says "lean" when the gap is within chance.
- **Promoting**: share the winner to everyone in the app. One blog says to re-upload it instead,
  without a source; it conflicts with Instagram's own description, so the editor does not do it.
- **Auto-share off during a test**, or two good versions can both reach followers. ([FavStash][favstash])

## Not the same thing

Instagram's April 2026 rule on reposted content ([Tubefilter][tube]) is aimed at aggregator accounts
reposting other people's work, and says speed changes alone are not "significant" edits. It does
not mention trials or a creator's own versions, but it is one more reason not to rely on speed-only
or caption-only differences.

## Open questions only his results can answer

- Does a fifth version of the same reel get less reach than the first? (`trial-learn`, by position)
- Which change wins most for him: hook text, a story-first opening, shorter, faster?
- Does a trial winner do better on the main feed than his reels did before trials? (compare with
  the insights export, see `stylebrain backtest`)

[ig]: https://creators.instagram.com/blog/instagram-trial-reels
[buffer]: https://buffer.com/resources/instagram-trial-reels/
[favstash]: https://www.favstash.app/blog/how-to-post-trial-reels
[adaptly]: https://adaptlypost.com/blog/instagram-trial-reels
[meta]: https://developers.facebook.com/blog/post/2025/12/03/instragram-api-updates/
[metadocs]: https://developers.facebook.com/docs/instagram-platform/content-publishing
[tube]: https://tubefilter.com/2026/04/30/instagram-removes-algorithm-recommendations-repost-content-aggregator
