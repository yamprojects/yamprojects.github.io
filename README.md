# הפרויקטים של ים

אתר תיק עבודות סטטי: HTML ו-CSS, בלי framework ובלי JavaScript.

```
python tools/build.py
```

הפקודה בונה את `public/` מחדש מ-`projects.json`, `templates/`, `images/` ו-`fonts/`.
כל מה שב-`public/` נוצר אוטומטית ונמחק בכל בנייה, אז עורכים רק את המקורות.

## להוסיף, לשנות או להוריד פרויקט

הכול ב-[projects.json](projects.json). כל פרויקט הוא רשומה אחת:

| שדה | מה זה |
|---|---|
| `slug` | מזהה באנגלית, משמש לשם הקובץ ולעוגן (`#slug`) |
| `name`, `subtitle` | השם, ושם משני אופציונלי |
| `category` | אחד מה-`id` שב-`categories` |
| `status` | אחד מהמפתחות שב-`statuses` (שוחרר, בפיתוח וכו') |
| `version` | אופציונלי, מוצג ליד הסטטוס |
| `summary` | משפט אחד |
| `highlights` | נקודות שנפתחות ב«עוד פרטים» |
| `tech` | תגיות טכנולוגיה |
| `image` | צילום מסך מתוך `images/`, נחתך ל-16:10 מהמרכז |
| `crop: "top"` / `fit: "contain"` | לחתוך מלמעלה / להציג את כל התמונה (ללוגו) |
| `art` | כשאין תמונה: כריכה מצוירת (`rings`, `wave3d`, `voice`, `agents`, `timing`, `waveform`, `hex`, `chip`, `letters`) |
| `accent`, `accent2` | צבעי הכרטיס והכריכה |
| `links` | כפתורים: `{ "label": "...", "url": "..." }` |

כדי להוריד פרויקט מוחקים את הרשומה שלו (ואת התמונה שלו מ-`images/`, אם יש) ובונים מחדש.

קישורים באתר מובילים רק לאתרים של הפרויקטים עצמם, אף פעם לא למאגרי הקוד ב-GitLab או ב-GitHub.

## טיוטות

ב-`drafts/` שמורים פרויקטים שכרגע לא מופיעים באתר: הרשומות שלהם ב-[drafts/projects.json](drafts/projects.json) והתמונות ב-`drafts/images/`.
כדי להחזיר פרויקט, מעבירים את הרשומה שלו ל-`projects.json` ואת התמונה ל-`images/`, ובונים מחדש.
התיקייה הזאת לא נכנסת למאגר הציבורי (היא ב-`.gitignore`).

## תצוגה מקדימה

```
python -m http.server 8766 --directory public
```

ואז לפתוח <http://localhost:8766>.

## תמונת התצוגה המקדימה

התמונה שמופיעה כשמשתפים קישור לאתר (וואטסאפ, טוויטר וכו') נמצאת ב-`images/og.png`, בגודל 1200×630.
אחרי שינוי בפרויקטים או בכותרת מייצרים אותה מחדש:

```
python tools/og.py
```

הסקריפט משתמש ב-Chrome או ב-Edge במצב headless, כי Pillow לא יודע לסדר כאן טקסט בעברית.
העיצוב שלה נמצא ב-`templates/og.html`.

## פרסום

GitHub Pages, באותה דרך כמו `hinachti-site`: ה-Action שב-[.github/workflows/pages.yml](.github/workflows/pages.yml)
מעלה את `public/` בכל push ל-`main`. שום דבר לא נבנה בשרת, ולכן את `public/` מקמטים כמו שהוא.

כשבוחרים את שם החשבון:

1. ב-GitHub יוצרים מאגר **ציבורי** וריק בשם `<שם>.github.io`, בלי README.
2. ב-[projects.json](projects.json) ממלאים את `site_url` ב-`https://<שם>.github.io/` ומריצים את `python tools/build.py`.
   בלי הכתובת הזאת אין באתר תמונת שיתוף, קישור canonical ו-sitemap, כי הם צריכים כתובת מלאה.
3. מחליפים את זהות ה-commit במאגר הזה לכתובת noreply של האתר, ומעדכנים את ה-commit הראשון.
4. מחברים את המאגר (`git remote add origin ...`) ודוחפים את `main`.
5. ב-GitHub: Settings ← Pages ← Source: **GitHub Actions**.
