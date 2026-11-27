# Hits vs flops, within each creator

Reach = log10(views / creator median). rho = Spearman rank correlation of the attribute with views inside one creator. n = clips with that attribute. |rho| under 0.3 is treated as nothing.


## mekluvin (n=27, median views 225,119, range 24,597 to 9,076,654)

Top 3: "This Made Me Quit The Gym 😭" 9,076,654; "Testing if Gymbros Lie" 3,927,422; "The Most INSANE Bench Challenge on YouTube 😳" 2,050,647

Bottom 3: "Challenging the BIGGEST Guy in My Gym" 59,830; "I Challenged The Biggest Guy In My Gym 😳" 46,433; "I Paid for EVERYONES Gas Because of THIS:" 24,597

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| words_per_minute | +0.60 | 148 | 118 | 6 |
| text_changes_per_10s | -0.40 | 17.5 | 27.9 | 27 |
| hook_question | +0.32 | 0.5 | 0 | 27 |
| motion | -0.31 | 4.75 | 5.41 | 27 |
| title_words | -0.31 | 6 | 7 | 27 |
| text_on_frame_1 | +0.31 | 1 | 1 | 27 |

## cbum (n=26, median views 52,989, range 15,510 to 817,576)

Top 3: "Nice warm-up" 817,576; "Let's not talk about bench😂" 395,118; "Gotta watch out for the EMF's🤷🏻‍♀️" 228,969

Bottom 3: "Accept the doubt, don't cut it out" 19,195; "Coming soon👀" 16,485; "You are capable of more than you think" 15,510

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| words_per_minute | +0.67 | 218 | 114 | 8 |
| seconds | -0.40 | 24 | 37 | 26 |

## vince (n=26, median views 28,904, range 5,520 to 262,694)

Top 3: "Any questions?" 262,694; "Each failure brings me closer to success" 111,843; "Ran out of shampoo" 95,354

Bottom 3: "Day 96/100, drop your check in Beast!" 12,375; "How to become disgustingly consistent and achieve anything" 9,472; "How’d you get after it today?" 5,520

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| saturation | +0.36 | 0.218 | 0.185 | 26 |
| speech_share | -0.33 | 1 | 1 | 26 |
| first_word_at | +0.32 | 0 | 0 | 22 |
| seconds | -0.31 | 34 | 43 | 26 |
| text_on_frame_1 | +0.31 | 1 | 1 | 26 |

## alex (n=24, median views 22,600, range 1,873 to 388,170)

Top 3: "Morning routine once you make it" 388,170; "Body dysmorphia" 153,082; "Fiancee tries crabs for the first time" 112,561

Bottom 3: "I Thought I Was Sick. It Was Anxiety." 3,266; "How to fix your anxiety" 2,219; "Mikey inspirational fr" 1,873

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| cuts_per_minute | +0.69 | 23.1 | 3.53 | 24 |
| median_shot | -0.67 | 2.02 | 14.7 | 24 |
| text_changes_per_10s | +0.50 | 4.25 | 0.205 | 24 |
| first_cut_at | -0.49 | 2.98 | 10.2 | 24 |
| text_on_frame_1 | +0.48 | 1 | 0 | 24 |
| hook_question | +0.45 | 0 | 0 | 24 |
| hook_me | -0.42 | 0 | 1 | 24 |
| contrast | -0.41 | 0.678 | 0.799 | 24 |
| words_per_minute | +0.37 | 120 | 75.5 | 14 |
| age_days | +0.36 | 81.4 | 30.1 | 24 |
| title_number | +0.34 | 0 | 0 | 24 |
| loop_gap | +0.34 | 41.6 | 9.78 | 24 |
| title_question | -0.32 | 0 | 0 | 24 |
| first_word_at | -0.30 | 0 | 0.4 | 21 |

## noah (n=20, median views 128,811, range 39,850 to 1,479,473)

Top 3: "Chasing a PR at the Chicago Marathon" 1,479,473; "Can I Break 2:20 in My First Olympic Triathlon?" 1,429,944; "My first Olympic triathlon" 446,212

Bottom 3: "Run 10k with me in Portugal" 58,714; "Be your weird" 53,541; "You're Only Limiting Your Own Potential" 39,850

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| loop_gap | +0.67 | 41 | 7.03 | 20 |
| words_per_minute | +0.66 | 273 | 205 | 19 |
| text_changes_per_10s | +0.57 | 27.5 | 18 | 20 |
| motion | +0.55 | 8.1 | 2.91 | 20 |
| hook_number | +0.55 | 1 | 0 | 20 |
| cuts_per_minute | +0.52 | 16 | 0 | 20 |
| first_cut_at | -0.47 | 2.29 | 59.9 | 20 |
| age_days | +0.46 | 52.7 | 27.8 | 20 |
| median_shot | -0.45 | 2.69 | 59.9 | 20 |
| longest_pause | +0.39 | 0 | 0 | 19 |
| cuts_in_first_3s | +0.35 | 1 | 0 | 20 |
| contrast | -0.32 | 0.695 | 0.723 | 20 |

## jun (n=20, median views 4,170, range 1,274 to 13,407)

Top 3: "so….I have some news" 13,407; "the MOST important choice" 8,786; "you DO NOT need fancy equipment" 7,532

Bottom 3: "The $1.5T Siblings" 2,301; "The Psychology of Storytelling" 1,335; "IT’S MY BIRTHDAYYYYY" 1,274

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| age_days | +0.47 | 28.2 | 26.6 | 20 |
| first_cut_at | +0.39 | 5.11 | 3.23 | 20 |
| hook_number | +0.39 | 1 | 0 | 20 |
| motion | +0.38 | 0.865 | 0.95 | 20 |
| hook_money | -0.34 | 0 | 0 | 20 |

## goodgood (n=20, median views 61,872, range 13,916 to 1,106,427)

Top 3: "Grant Horvat reacts to this swing.. 😂" 1,106,427; "Oh no Matt Scharff 😂" 324,646; "Worst thing that can happen.. happened" 240,308

Bottom 3: "Bubbie Golf makes it look easy.." 23,859; "Another Good Good debate.." 19,382; "Good Good game gone wrong 😂" 13,916

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| text_share | -0.36 | 0.224 | 0.344 | 20 |
| text_changes_per_10s | +0.36 | 3.88 | 0.56 | 20 |
| cuts_in_first_3s | +0.33 | 0 | 0 | 20 |

## japes (n=20, median views 67,810, range 1,289 to 436,492)

Top 3: "Is This The BEST Golf Resort😳 (WYNN Las Vegas)" 436,492; "Worst Ball Birdie!?!😳 (INSANE)" 244,812; "THE LONGEST PAR 4 IN FLORIDA 😳" 190,932

Bottom 3: "JAPES VS TY (CHANCE TAYLOR COMMENTARY)😂" 26,114; "JP & George YGT (ALT SHOT) 1 of 3 birdies in 4 holes 😳" 18,995; "The #1 Golf Resort In Utah 😳😳😳" 1,289

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| text_on_frame_1 | +0.59 | 0 | 0 | 20 |
| title_question | +0.52 | 0 | 0 | 20 |
| warmth | +0.31 | 0.084 | 0.0415 | 20 |

## solidheaston (n=20, median views 121,018, range 4,835 to 6,105,863)

Top 3: "Imma miss that parking lot 😢 #carcamping #fitnessinfluencer " 6,105,863; "Making these videos is destroying brain holy cow. #carcampin" 1,617,531; "I’m dropping to 180lbs ASAP #hyrox #hyroxworld #fitnessinflu" 1,257,824

Bottom 3: "YouTube recommendation of the week #degen #unemployed #fitne" 33,858; "I wasted so much time. #handstand #calisthenics #fitnessinfl" 22,838; "Isometrics on top #hyrox #gymlife #fitnessmotivation #baki #" 4,835

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| words_per_minute | +0.71 | 212 | 154 | 20 |
| cuts_in_first_3s | +0.56 | 1 | 0 | 20 |
| first_cut_at | -0.55 | 2.92 | 40.5 | 20 |
| cuts_per_minute | +0.54 | 13 | 0.5 | 20 |
| speech_share | +0.53 | 1 | 1 | 20 |
| first_word_at | -0.53 | 0 | 0 | 20 |
| text_changes_per_10s | +0.52 | 8.18 | 0.665 | 20 |
| hook_you | -0.52 | 0 | 0 | 20 |
| motion | +0.52 | 5.76 | 5.09 | 20 |
| median_shot | -0.47 | 2.69 | 59.7 | 20 |
| text_share | +0.46 | 0.347 | 0.077 | 20 |
| hook_words | +0.43 | 11 | 8 | 20 |
| hook_me | +0.40 | 1 | 1 | 20 |
| zoom_events_per_minute | +0.39 | 0.5 | 0 | 20 |
| hook_question | -0.38 | 0 | 0 | 20 |
| brightness | +0.38 | 0.504 | 0.48 | 20 |
| longest_pause | -0.31 | 0 | 0 | 20 |
| age_days | +0.30 | 130 | 110 | 20 |

## luka (n=15, median views 1,139, range 348 to 4,416)

Top 3: "Y-T-W Exercise To Build Your Upper Back" 4,416; "50 lb Added Weight Rope Climb For Relative Upper Body Streng" 3,433; "Women's Athlete For Life Training at Vigor Ground Fitness" 2,183

Bottom 3: "360 Degrees Coaching To Improve Your Personal Training" 538; "4 Factors When Programming For Longevity" 455; "Gym Marketing Language To Improve Results" 348

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| loop_gap | +0.70 | 23.9 | 4.89 | 15 |
| speech_share | -0.64 | 0.4 | 1 | 15 |
| seconds | -0.58 | 52.5 | 69 | 15 |
| hook_me | -0.54 | 0 | 0 | 15 |
| warmth | +0.52 | 0.0665 | 0.045 | 15 |
| first_word_at | +0.47 | 0.38 | 0 | 10 |
| text_changes_per_10s | -0.45 | 6.02 | 35.5 | 15 |
| hook_you | -0.43 | 0 | 1 | 15 |
| hook_question | -0.42 | 0 | 0 | 15 |
| text_share | -0.33 | 0.33 | 0.7 | 15 |
| age_days | +0.33 | 105 | 42.2 | 15 |

## youngdalt (n=8, median views 3,484, range 1,989 to 105,281)

Top 3: "1v1 against my good buddy, Chance Taylor." 105,281; "INSANE start to our match." 83,799; "This hole is nuts 🫪 #golf #ygt #vegas #wynn #youtubegolf" 5,430

Bottom 3: "$1000 round in Vegas. Worth it. #golf #sphere #youtubegolf #" 2,604; "🥶🥶🥶 #golf #snow #golfer" 2,384; "About a week out, dialing it in. New YT video is live. #golf" 1,989

| attribute | rho | median, top half | median, bottom half | n |
|---|---|---|---|---|
| median_shot | +0.88 | 9.02 | 5.38 | 8 |
| motion | +0.86 | 4.69 | 1.57 | 8 |
| age_days | +0.71 | 126 | 69 | 8 |
| speech_share | +0.66 | 0.966 | 0 | 8 |
| loop_gap | +0.62 | 30.5 | 21.5 | 8 |
| cuts_per_minute | -0.60 | 5.02 | 9.52 | 8 |
| hook_words | +0.48 | 4 | 0 | 8 |
| first_cut_at | +0.43 | 8.72 | 6.48 | 8 |
| hook_you | +0.41 | 0 | 0 | 8 |
| hook_question | +0.41 | 0 | 0 | 8 |
| seconds | +0.41 | 59 | 61 | 8 |
| title_words | -0.38 | 8.5 | 10.5 | 8 |
| warmth | +0.33 | 0.05 | -0.0085 | 8 |
| brightness | -0.33 | 0.512 | 0.502 | 8 |

## Across creators
How many creators show the same direction (|rho| >= 0.3). An attribute that points the same way for several creators is steadier than one strong result.

| attribute | creators: more = more views | creators: more = fewer views | creators tested |
|---|---|---|---|
| age_days | 6 | 0 | 11 |
| words_per_minute | 5 | 0 | 9 |
| text_on_frame_1 | 4 | 0 | 10 |
| loop_gap | 4 | 0 | 11 |
| cuts_in_first_3s | 3 | 0 | 10 |
| motion | 4 | 1 | 11 |
| warmth | 3 | 0 | 11 |
| seconds | 1 | 3 | 11 |
| cuts_per_minute | 3 | 1 | 11 |
| median_shot | 1 | 3 | 11 |
| text_changes_per_10s | 4 | 2 | 11 |
| contrast | 0 | 2 | 11 |
| hook_number | 2 | 0 | 11 |
| title_words | 0 | 2 | 11 |
| hook_words | 2 | 0 | 6 |
| first_cut_at | 2 | 3 | 11 |
| text_share | 1 | 2 | 11 |
| zoom_events_per_minute | 1 | 0 | 9 |
| saturation | 1 | 0 | 11 |
| hook_question | 3 | 2 | 9 |
| hook_you | 1 | 2 | 8 |
| hook_me | 1 | 2 | 10 |
| hook_money | 0 | 1 | 3 |
| title_number | 1 | 0 | 11 |
| brightness | 1 | 1 | 11 |
| first_word_at | 2 | 2 | 10 |
| speech_share | 2 | 2 | 11 |
| title_question | 1 | 1 | 10 |
| longest_pause | 1 | 1 | 5 |
