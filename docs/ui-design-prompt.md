# Återanvändbar UI-designprompt: galleri med data som bild

Prompten nedan gav Seismo-sidan sitt utseende. Byt ut orden inom [hakparenteser] och klistra in den i en ny session.
Den är skriven för React + Vite, men designresonemanget gäller vilket ramverk som helst.

## Lärdomar som prompten bygger på

1. **Titta på referensens estetik, inte bara layouten.** Första försöket kopierade bara upplägget (svart bakgrund,
   rutnät, hashtag-filter) och blev generiskt. Det som gjorde referensen särskild var projektens visuella språk:
   LED- och ljuskonst på ren svart, lysande punkter och pixelrutor, vertikala ljusströmmar, en mättad färg per verk,
   glöd och en pixellogotyp. Öppna referenssidan i webbläsaren, ta skärmbilder av flera verk och beskriv det som
   återkommer innan du skriver någon kod.
2. **Låt datat vara bilden.** Referensens rutor är bilder eller video. Här ritas varje ruta av appens egen data
   (positioner, storlekar, antal) och animeras med CSS. Då är designen ärlig och ser levande ut utan externa tillgångar.
3. **En accentfärg per verk, och bara en.** Färgen styr ruta, rubrikmarkör och fokus i detaljvyn. Låt ett test
   garantera att färgerna är unika.
4. **Kopiera aldrig innehåll.** Ta inspiration av uttryck och struktur. Använd inga bilder, texter eller logotyper
   från referensen.
5. **Verifiera visuellt.** Kör sidan, ta skärmbild på skrivbordsbredd och på smal skärm, och titta på resultatet.
   Typecheck och tester säger inget om hur det ser ut.

## Prompten

```text
Redesigna [appens frontend] efter den samlade estetiken på [URL till referenssidan].

Steg 1, analysera (skriv ingen kod än):
- Öppna referenssidan i webbläsaren och scrolla igenom den. Ta skärmbilder av flera av verken.
- Beskriv två saker separat: (a) layouten (rutnät, navigation, filter, bildtexter) och (b) estetiken i själva
  verken (färger, former, material, rörelse, typografi, logotyp). Det är (b) jag vill att designen bygger på,
  inte bara (a).
- Sammanfatta den visuella identiteten i fem punkter och visa mig dem innan du bygger.

Steg 2, designa:
- Startsida: ett galleri med en ruta per vy. Rutorna är stående (4:5), utan ram, med titel och en kort
  kursiv beskrivning under. Hashtag-filter ovanför (#alla plus taggar som faktiskt ger minst en ruta).
- Varje ruta har en egen mättad accentfärg och en förhandsvisning som ritas av appens riktiga data och animeras
  med CSS. Inga stockbilder, inga externa tillgångar.
- Detaljvyer öppnas från rutorna med hash-routing (fungerar på GitHub Pages), en "← tillbaka"-länk och fokus
  som flyttas till rubriken vid navigering.
- Svart bakgrund, dämpad grå text, minimal textmeny uppe till höger, pixellogotyp byggd av en bitmap.
- Kartor och diagram i mörkt tema, med samma färgkodning som legenden. Legenden och kartan ska läsa färgerna
  från en och samma källa.

Krav:
- Tillgängligt: tangentbordsnavigering, synlig fokusmarkering, aria-etiketter, prefers-reduced-motion stänger av
  all animation. Dekorativa förhandsvisningar är aria-hidden.
- Fungerar på smal skärm (280 px) utan sidscroll i sidled.
- Inget kopierat innehåll från referensen.
- Uppdatera tester efter ombyggnaden. Kör typecheck, lint, tester och bygge.
- Verifiera visuellt i webbläsaren på skrivbordsbredd och mobilbredd och visa mig vad du ser.
- Säg ärligt vad du inte har kontrollerat.

Språk: [svenska/engelska]. Skriv kort och rakt, utan utsmyckade fraser.
```

## Anpassa per projekt

- **Annan referens:** byt URL och gör steg 1 på nytt. Estetiken (LED på svart) är bara svaret för just den referensen.
- **Annan data:** förhandsvisningarna måste ritas av det datat. Exempel: tidsserier blir pixelstaplar, geografi blir
  en punktmatris, flöden blir noder med en vandrande puls.
- **Ljust tema:** samma struktur fungerar. Byt svart mot en off-white yta och låt accentfärgerna bära uttrycket.
