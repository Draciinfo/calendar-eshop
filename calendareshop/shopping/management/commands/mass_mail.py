# -*- coding: utf-8 -*-
import logging
import re
import datetime

from django.core.management.base import BaseCommand
from post_office import mail
from django.conf import settings

from calendareshop.models import NewsletterSubscription
from shopping.models import CustomOrder, email_hash

logger = logging.getLogger(__name__)
settings.EMAIL_BACKEND = 'post_office.EmailBackend'


email_footer = u'<span style="color: #888;">Pokud si nepřejete tyto emaily nadále odebírat, odpovězte na tento email a do těla zprávy napište "odhlásit".</span><br>'

class MailGroup:
    MEMBERS = 1
    CUSTOMERS = 2


def get_emails_from_file(file_name):
    with open(file_name, 'r') as f:
        return set(map(lambda x: x.strip(), f.readlines()))


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--doit', dest='doit', action='store_true', default=False)
        parser.add_argument('--send-test', dest='send_test', action='store_true', default=False)

    def handle(self, *args, **options):
        doit = options['doit']
        send_test = options['send_test']

        year = datetime.datetime.today().year + 1

        blacklist = get_emails_from_file('blacklist.txt')

        mail_group = MailGroup.MEMBERS

        sent_emails = set()
        emails = set()
        if mail_group == MailGroup.CUSTOMERS:
            # substract member mails from customer mails
            sent_emails = get_emails_from_file('member_mails.txt')
            emails.update(list(CustomOrder.objects.filter(personal_information_consent=True, language_code='cs').values_list('email', flat=True)))
            emails.update(list(NewsletterSubscription.objects.values_list('email', flat=True)))
        elif mail_group == MailGroup.MEMBERS:
            emails = get_emails_from_file('member_mails.txt')

        emails -= sent_emails
        emails -= blacklist
        count = len(emails)
        print emails
        print count
        if send_test:
            emails = [
                'flaiming@gmail.com',
                'kitty@draci.info',
                'exander77@gmail.com',
                'kaarhai@gmail.com',
            ]
            count = len(emails)
        logger.info('Total of emails that will be send: %s', count)

        email_pre_preorder = (
            u"Připravujeme předobjednávky kalendáře Draci.info %s" % year,
            u"""Pěkný den,

i tento rok budeme vydávat dračí kalendář od tvůrců z <a href="https://draci.info">Draci.info</a>.
V současné době naši členové čile pracují na obrázcích do kalendáře.
Držíme se stejného harmonogramu jako minulý rok, <b>předobjednávky otevřeme na přelomu září a října</b>. Kalendáře budeme následně rozesílat během listopadu.

Přejeme Vám pěkné léto a těšíme se na Vás na podzim s novým kalendářem!

Organizační tým projektů Draci.info""")

        email_preorder = (
            u"Předobjednávky kalendáře Draci.info %s jsou otevřeny!" % year,
            u"""Pěkný den,

<a href="https://kalendar.draci.info/">kalendář Draci.info 2020</a> je nyní v předprodeji!
I letos se můžete těšit na 13 dračích obrázků od českých a slovenských autorů z Draci.info.
Hotové kalendáře budeme rozesílat do nových domovů v polovině listopadu - po předprodeji bude k dispozici pouze omezené množství kalendářů, proto doporučujeme předobjednat kalendář co nejdříve.

Děkujeme za Vaši přízeň a přejeme krásný, barevný podzim!

Organizační tým projektů Draci.info""".format(year=year))

        email_members = (
            u"Předobjednávka kalendáře %s pro členy draci.info otevřena!" % year,
            u"""Ahoj!

Jako členovi Draci.info Ti nabízíme kalendář Draci.info a pexeso za speciální cenu.

<b>Jak objednat?</b>
1) Sečti ceny produktů, které si chceš objednat a připočti poštovné. (ceny viz níže)
2) Pošli platbu na <b>infácký účet 2901050776 / 2010</b> do zpráy pro příjemce napiš svou přezdívku na infu a obsah objednávky
3) Odpověz na tento email NEBO napiš Kay vzkaz obsahující: info za co jsi zaplatil(a) + reálné jméno a adresa, nebo info o vyzvednutí na sletu

<b>Ceny</b>
Nástěnný kalendář {year}: 140 Kč/ks
Pexeso: 15 Kč *

<b>Poštovné</b>
Poštovné za 1 kalendář po ČR = 80 Kč
Poštovné za 2-4 kalendáře po ČR = 90 Kč
Poštovné za 1 kalendář do SK = 190 Kč
Poštovné za 2 kalendáře do SK = 270 Kč
Poštovné za 3-4 kalendáře do SK = 410 Kč
* Pexeso poštou lze pouze s kalendářem, poštovné se počítá pouze za kalendář.

(Pokud si nebudeš vědět rady s výpočtem poštovného, napiš Kay)

<b>Kalendáře budou rozesílány/rozdávány na konci října.</b>

<b>Autoři</b>
Každý autor má nárok na 1 kus kalendáře zdarma a to včetně poštovného na celou objednávku.

Těšíme se na tvou objednávku!

Organizační tým projektů Draci.info""".format(year=year))


        email_members2 = (
        u"Předobjednávky kalendáře končí ve čtvrtek!",
        u"""
Ahoj!
Pokud ještě váháš s objednávkou kalendáře, je nejvyšší čas se rozhoupat!<br>
<b>Předobjednávky přijímáme do čtvrtka 31.10.2019</b> - nejpozději tento den musí být platba připsána na účet Draci.info.<br>
Máš-li již objednáno a zaplaceno, omlouváme se za spam a děkujeme :D

Do zásoby nakoupíme jen velmi malé množství, není tedy dobrý nápad čekat déle a spoléhat se na to, že kalendáře ještě budou. Prodej ze skladových zásob navíc bude dražší.


Pokud máš jakýkoli dotaz, nebo si chceš objednat, stačí odpovědět na tento email. Podrobné info k objednávkám najdeš buď na Draci.info v příslušném <a href="https://draci.info/index.php?cls=forum&id=153">fóru</a>, nebo v předchozím emailu.

Organizační tým projektů Draci.info""".format(year=year))

        email_table_calendar = (
            u"Předobjednávka stolního kalendáře Draci.info %s" % year,
            u"""Krásný podzimní den!

S radostí Vám oznamujeme, že tento rok poprvé nabízíme veřejnosti i <b>stolní dračí kalendář</b>!
Předobjednat si ho můžete v našem <a href="https://kalendar.draci.info/">eshopu</a> za 250 Kč.
Tisk i rozesílání proběhne společně s nástěnnými kalendáři koncem listopadu.

Pokud máte zájem o stolní i nástěnný kalendář, připravili jsme pro Vás <b>speciální balíček za výhodnou cenu</b>!
Vše najdete na eshopu.

<img src="https://kalendar.draci.info/static/img/stolni_kalendar_2019_1.jpg" style="width: 100%;" />
<img src="https://kalendar.draci.info/static/img/stolni_kalendar_2019_2.jpg" style="width: 100%;" />

Těšíme se na Vaše objednávky.

Organizační tým projektů Draci.info""".format(year=year))

        email_almost_sent = (
                u"Kalendáře Draci.info %s budou již brzy" % year,
            u"""Krásný den!

Omlouváme se za zpoždění, museli jsme učinit pár změn s naším letošním tiskařem, ovšem kalendáře jsou již zadané k tisku a začneme je rozesílat hned jak budou hotové, tedy v průběhu příštích dvou týdnů.

Děkujeme Vám za trpělivost, uděláme vše pro to, abychom Vám dodali kalendáře Draci.info do Vánoc :)

Organizační tým projektů Draci.info""".format(year=year))

        email_partially_sent = (
                u"Odesíláme kalendáře Draci.info %s" % year,
            u"""Krásný den,

kalendáře Draci.info {year} jsou hotové! Dnes jsme odeslali prvních 30 a v nejbližší době pošleme zbytek :)

<img src="https://kalendar.draci.info/static/img/kalendar2019_hotovo.jpg" style="width: 100%;" />

Organizační tým projektů Draci.info""".format(year=year))

        email_final = (
                u"Kalendáře Draci.info %s odeslány" % year,
            u"""Krásný den,

s radostí Vám oznamujeme, že již máme odeslanou naprostou většinu kalendářů.
Dnes odesíláme poslední várku, takže do Vánoc je všichni budete mít doma.

<img src="https://kalendar.draci.info/static/img/kalendar2019_hotovo2.jpg" style="width: 100%;" />


Organizační tým projektů Draci.info""".format(year=year))

        email_feedback = (
            u"Spokojenost s kalendářem Draci.info %s" % year,
            u"""Krásný den,

Další rok je za námi a my doufáme, že se Vám kalendáře 2019 líbí a dorazily v pořádku.

Letošní vydání řešil po deseti letech zcela nový tým a i přes nečekané komplikace a zpoždění se vše podařilo dovést do zdárného konce. Navázání na "zaběhnutý" projekt nebylo úplně hladké, jelikož bylo potřeba vytvořit zcela nové podklady pro tisk. Určitě jste si všimli, že je design trochu jiný a věříme, že je pro Vás takto přehlednější a čitelnější. Také jsme chtěli zachovat naše tradiční verše, které k dračímu kalendáři neodmyslitelně patří.

Děkujeme Vám za trpělivost a slibujeme, že díky nabytým zkušenostem zvládneme příští ročník rychleji a lépe!

Nezapomeňte na dvanáctistěn na poslední straně kalendáře, jsou na něm obrázky z předchozích ročníků jako upomínka na dlouhou historii tohoto projektu. Budeme rádi, když nám pošlete fotku, pokud jste si ho vystřihli a slepili :)

Závěrem ještě přikládáme malý dotazník, zpětnou vazbu od Vás si ceníme.

<a href="https://goo.gl/forms/LbFF1DgGljPexaYn1">https://goo.gl/forms/LbFF1DgGljPexaYn1</a>

Přejeme Vám veselý Dračí rok 2019!

Organizační tým projektů Draci.info""".format(year=year))

        current_email = email_members2
        subject = ('TEST ' if send_test else '') + current_email[0]
        text = current_email[1]

        logger.info(u'Sending email:\nSubject: %s\nText:\n%s', subject, text)
        for email in emails:
            if doit:
                mail.send(
                    [email],
                    u'Kalendář Draci.info <kalendar@draci.info>',
                    template='default_cs',
                    context={
                        'domain': 'http://kalendar.draci.info',
                        'subject': subject,
                        'content_html': text.replace('\n', '<br />\n'),
                        'content_text': re.sub(r'<a href="([^"]*)"[^>]*>([^<]+)</a>', '\\2 \\1 ', re.sub('</?(?:b|small)>', '', text), flags=re.U),
                        'footer_text': email_footer,
                    },
                )


