# Archiv kalendářů Draci.info

Web funguje jako statický archiv ročníků 2012–2023.
Hotové stránky jsou v `archive/cs/` pro `kalendar.draci.info` a v `archive/en/`
pro `calendar.draci.info`. Každý adresář lze samostatně nasadit na běžný
statický hosting. Pro jejich provoz není potřeba Python, Django ani databáze.

Archiv zachovává původní vzhled, adresy ročníků, ilustrace v plné velikosti,
autory, historii a informační stránky v obou jazycích. Každá stránka oznamuje
ukončení vydávání kalendářů. Objednávkové prvky, přepínání měn, newsletter,
jeho formuláře a původní JavaScript včetně analytiky jsou odstraněny.
Galerie a mobilní navigace používají malý lokální skript bez síťových volání.
Obrázky, styly i písma jsou uložené lokálně.

Obchodní podmínky a dokument o osobních údajích zůstávají jako historické
dokumenty s výslovným označením. Obsah archivu pochází z veřejně dostupného
webu; databázové exporty ani lokální členské soubory se do něj nekopírují.
`archive/manifest.json` zaznamenává čas exportu, zdrojové adresy a kontrolní
součty původního HTML. Dne 31. října 2026 byl archiv nasazen na obě produkční
domény na serveru `oram.cz`; původní Django proces byl odstaven.

Produkční vydání je `/www/calendar-archive/releases/20261031T214133Z`,
odkaz `/www/calendar-archive/current` na něj směruje oba weby. Nginx používá
konfiguraci z `/www/calendar-archive/config/`; soubory v tomto repozitáři
`calendareshop/confs/archive/` odpovídají tomuto umístění.

Záloha původní konfigurace a skript pro návrat jsou v
`/www/calendar-archive/backups/20261031T214133Z/`. Návrat k Djangu se provede
na serveru jako `flaim` příkazem:

```sh
sh /www/calendar-archive/backups/20261031T214133Z/rollback.sh
```

Původní aplikace, databáze a média zůstaly zachované v původním umístění.
Spouštěcí odkaz kalendářového uWSGI byl přesunut mimo sledovaný adresář do
`/etc/uwsgi-python/calendar.ini.disabled-20261031T214133Z`.

## Lokální náhled

```sh
python3 scripts/serve_archive.py
# http://127.0.0.1:8000/
# http://127.0.0.1:8000/en/
```

Náhled obsluhuje oba jazyky a přepisuje jejich odkazy pouze v odpovědích
lokálního serveru. Přepínání jazyků i procházení ročníků proto zůstává lokální.
Hotové soubory pro nasazení nadále používají původní produkční adresy.
Případně lze zvolit jiný port pomocí `--port 8080`.

## Ověření a opakovaný export

Tyto nástroje potřebuje pouze správce při tvorbě nebo kontrole archivu,
nikoli návštěvníci nebo webový server. Použijte Python 3.10 nebo novější:

```sh
python3 -m venv .venv-archive
.venv-archive/bin/pip install -r scripts/requirements.txt
.venv-archive/bin/python scripts/freeze_site.py --verify-only
.venv-archive/bin/python -m unittest discover -s scripts -p 'test_*.py'
node --check scripts/archive.js
```

Nový export z veřejného webu se vytváří příkazem:

```sh
.venv-archive/bin/python scripts/freeze_site.py
```

Exportér čte jen veřejné stránky přes GET. Stahuje ročníky a informační
stránky, které najde v odkazech; neprochází administraci, objednávky ani
hlasování. Stažené podklady ukládá do ignorované `.archive-cache/`.
`--offline` umožňuje opakovat export z této cache bez připojení.
Pro načtení aktuálního stavu webu přesuňte původní cache stranou a spusťte
export znovu. Po vypnutí Djanga je zdrojem pro nasazení hotový adresář
`archive/`; samotný exportér už původní dynamické stránky nenahradí.

Při exportu se kontroluje existence lokálních odkazů, obrázků, stylů a písem
i odstranění formulářů a původních skriptů. Chybný export nenahradí předchozí
archiv. Současný web odkazuje na neexistující Font Awesome WOFF2; archiv
používá jeho dostupné WOFF/TTF varianty.

## Nasazení místo Djanga

1. Zkopírujte hotový `archive/` na server. Kořen českého webu musí být
   `archive/cs`, anglického `archive/en`.
2. Připravena je náhradní konfigurace
   `calendareshop/confs/archive/nginx.conf` a společná část `common.conf`.
   Upravte absolutní cesty podle serveru a ponechte správné cesty k TLS
   certifikátům. Tato konfigurace **nahrazuje** původní konfiguraci, nepřidává
   se vedle ní pro stejné domény. Původní konfiguraci si uschovejte pro návrat.
3. Ověřte konfiguraci pomocí `sudo nginx -t` a pak načtěte změny pomocí
   `sudo systemctl reload nginx`.
4. Na obou doménách ověřte titulní stránku, některý starší ročník, galerii a
   kontakt. `/newsletter/`, `/admin/` a staré objednávkové adresy vracejí 410;
   požadavky kromě GET a HEAD vracejí 405. Neznámé stránky mají skutečný stav
   404. HTTPS a obnova certifikátů přes HTTP zůstávají podporované.
5. Po kontrole lze vypnout původní uWSGI proces a související plánované úlohy
   (například rozesílání e-mailů). Statický web je už nepoužívá. Služby a
   konkrétní úlohy záleží na konfiguraci produkčního serveru.

Kořeny webů obsahují výhradně veřejné statické soubory. Nginx nikam
nepředává požadavky do Djanga a přes Content Security Policy zakazuje
odesílání formulářů a síťové požadavky JavaScriptu.

## Původní Django aplikace

Původní zdrojový kód a existující lokální změny jsou zachované. Následující
historický návod se vztahuje k někdejšímu e-shopu, ne ke statickému archivu.

## Installation

Prerequisities:

* Python 2.7


Very basic local installation:
```python
# Create and activate virtualenv.
mkdir ~/calendar-eshop  # or where you want it to be
cd ~/calendar-eshop
# if not already installed, install virtualenv and activate it.
pip install virtualenv
virtualenv .
source bin/activate

# Install site and dependencies.
git clone https://github.com/Draciinfo/calendar-eshop.git
cd calendar-eshop 
pip install -r requirements.txt

# install developement requirements if needed
pip install -r requirements_dev.txt

# Create and edit local settings to match your setup. 
cd calendareshop
cp calendareshop/settings/local_[prod|dev]_example.py calendareshop/settings/local.py
vim calendareshop/settings/local.py

# Prepare database and load initial data.
./manage.py migrate
./manage.py createsuperuser
./manage.py collectstatic
```
