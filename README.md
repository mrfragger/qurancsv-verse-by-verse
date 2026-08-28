# Quran csv verse-by-verse

Convert Quran with audio for each ayah from either everyahah.com or quranenc.com
with subtitles using 82 csv translations.  The csv references the surah and ayah 
of each audio which corresponds with the audio of each audio mp3.  

Like ```002255``` references ```surah 2 ayah 255``` for instance. Subtitles can pretty much be 80 characters long otherwise subs get super small so the ayah needs to be intelligently divided up with up to 6 breaks depending on character length of ayah.  This is done super fast but for ```Japanese, Chinese, Thai and Khmer``` it needs to tokenize each word so it knows where to make the breakpoint rather than breaking in the middle of a word.

### original subtitles from csv before being split if over 80 characters
```
2,13,"And when it is said to them, ""Believe as the people have believed,"" they say, ""Should we believe as the foolish have believed?"" Unquestionably, it is they who are the foolish, but they know [it] not.",وَإِذَا قِيلَ لَهُمْ ءَامِنُوا۟ كَمَآ ءَامَنَ ٱلنَّاسُ قَالُوٓا۟ أَنُؤْمِنُ كَمَآ ءَامَنَ ٱلسُّفَهَآءُ ۗ أَلَآ إِنَّهُمْ هُمُ ٱلسُّفَهَآءُ وَلَٰكِن لَّا يَعْلَمُونَ,002013.mp3
2,14,"And when they meet those who believe, they say, ""We believe""; but when they are alone with their evil ones, they say, ""Indeed, we are with you; we were only mockers.""",وَإِذَا لَقُوا۟ ٱلَّذِينَ ءَامَنُوا۟ قَالُوٓا۟ ءَامَنَّا وَإِذَا خَلَوْا۟ إِلَىٰ شَيَٰطِينِهِمْ قَالُوٓا۟ إِنَّا مَعَكُمْ إِنَّمَا نَحْنُ مُسْتَهْزِءُونَ,002014.mp3
```

### splitting 
```
00:01:34.688 --> 00:01:40.673
2,13 When it is said to them, “Believe as the people have believed,” they say, “Shall we believe

00:01:40.673 --> 00:01:46.659
as the fools have believed?” Indeed, it is they who are the fools, but they do not know.

00:01:46.659 --> 00:01:51.233
2,14 When they meet those who believe, they say, “We believe.” But when they are alone

00:01:51.233 --> 00:01:55.808
with their evil ones, they say, “We are certainly with you; we were only mocking.”
```

```download.py``` and ```files.json``` is for downloading audio using api of quranenc.com

```duration_report.sh``` is used to gather duration of audiobooks like so

- 17h 54m Assamese - (Rafeeq)
- 19h 07m Chinese - (Suleiman)
- 18h 27m Dutch - (Rowwad)
- 13h 13m English - (Rowwad)
- 14h 30m French - (Rashid)
- 25h 26m Persian - (Rowwad)
- 14h 47m Portuguese - (Nasr)
- 28h 08m Sinhalese - (Rowwad)
- 20h 25m Somali - (Yaqoub)
- 24h 05m Tagalog - (Rowwad)
- 19h 25m Vietnamese - (Rowwad)

versebyversequran.zip 36 MB unzips to ~ 139 MB

contains 82 csv translations from quranenc.com as well as the 7 split csv files of the English Sahih International translation.
- quran_saheeh001-006.csv
- quran_saheeh007-015.csv
- quran_saheeh016-024.csv
- quran_saheeh025-036.csv
- quran_saheeh037-049.csv
- quran_saheeh050-069.csv
- quran_saheeh070-114.csv

These are then processed for the timings of the quran audiobooks.  Does not matter which language as long as their is an official quran translation for it in csv then the default English can be overwritten to whichever language.


##                 zqurancsv.py

##         Combined Quran CSV Processing Pipeline

### Steps:
### A. Organize mp3 media into range subdirectories like so:
- quran_saheeh001-006_media
- quran_saheeh001-006_media
- quran_saheeh007-015_media
- quran_saheeh016-024_media
- quran_saheeh025-036_media
- quran_saheeh037-049_media
- quran_saheeh050-069_media
- quran_saheeh070-114_media

This can be done automatically by putting all mp3 into a subdir named quranversebyverse then choosing 3. Organize mp3 media into range subdirectories

### === Organize MP3 media files into range subdirectories ===

### Moved 6236 mp3 files into range subdirectories.
Left 112 bismillah file(s) (ayah 000) in place, not moved.
- quran_saheeh001-006_media/: 954 files
- quran_saheeh007-015_media/: 947 files
- quran_saheeh016-024_media/: 954 files
- quran_saheeh025-036_media/: 933 files
- quran_saheeh037-049_media/: 842 files
- quran_saheeh050-069_media/: 745 files
- quran_saheeh070-114_media/: 861 files
(which totals 6236 ayahs)

### Once that is done use SubSticher to make opus chaptered audiobooks with csv 
(Anki convert to audiobook and choose csv)

Language put Quran Arabic or Quran English
Title should automatically fill with ```001-006``` depending on which csv is chosen 
and put reciters name after ```001-006```
example: ```Quran Arabic - 007-015 Ghamadi Verse by Verse```

Audio Repetitions ```1x``` (2x, 3x, 4x are for anki audiobooks)
Bitrate ```32 kpbs``` (since recitations are not purely speak)

check ```Use filename as chaptername``` so ```surah 2 ayah 5``` is ```002005``` rather 4 digits
uncheck ```Sample Mode``` (50 entries)
check ```Prepend Sura/Aya to subtitles```
check ```Match media by range``` (this automatically change 001-006 to 070-114 corresponding to selected  csv)

Front column ```translation``` (this is the chapter name)
Back Column ```arabic``` (does not matter though only for 2x, 3x, 4x repetitions)
Audio Column ```audio``` (this is the mp3)
Sura Column ```sura``` (adds surah number before each verse in the vtt subs)
Aya Column ```aya``` (adds ayah number before each verse in the vtt subs)

Subsequent audiobooks just choose the next csv and it autofills the surah numbers
and then in Column Selection section click ```Use Last (3,4,5, Sura 1, Aya 2)```
so need not manually fill in again

### B. Remove translation info header, id column, footnotes column
### C. Normalize Arabic transliteration characters, remove reference & verse numbers
### D. Split into 7 range-based files (001-006, 007-015, etc.)
### E. Add Arabic text and audio from quran_saheeh source files
### F. (Optional) Generate translated VTT files from existing English VTT source files (long subtitle cues are automatically split into shorter ones → zsplit/Language/)
### G. (Optional) Zip zsplit folder for distribution

### For Japanese, Chinese, Thai, and Khmer tokenization, install:
```  pip3 install jieba sudachipy SudachiDict-core pythainlp[attacut] khmer-segmenter```

Make sure to have in the root dir (reciter subs generated with SubStitcher):
- qurancsv.py
- Quran Arabic - 001-006 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 001-006 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 007-015 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 007-015 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 016-024 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 016-024 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 025-036 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 025-036 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 037-049 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 037-049 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 050-069 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 050-069 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- Quran Arabic - 070-114 Abu Bakr Ash-Shaatree Verse by Verse.opus
- Quran Arabic - 070-114 Abu Bakr Ash-Shaatree Verse by Verse.vtt
- quran_saheeh001-006.csv
- quran_saheeh007-015.csv
- quran_saheeh016-024.csv
- quran_saheeh025-036.csv
- quran_saheeh037-049.csv
- quran_saheeh050-069.csv
- quran_saheeh070-114.csv

### And all translation CSV files in their respective subdirs:
- french/french_montada_v1.0.0-csv.1.csv
- german/german_bubenheim_v1.1.4-csv.1.csv
- etc.
