# -*- coding: utf-8 -*-
import hashlib
import datetime
from collections import OrderedDict

from django.conf import settings
from django.db import models
from django.core.urlresolvers import reverse


class BaseVotingManager(models.Manager):

    def this_year(self):
        return self.get_queryset().filter(date_created__year=datetime.date.today().year)


class Voter(models.Model):
    date_created = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    voting_finished = models.BooleanField(default=False)

    author = models.OneToOneField('calendareshop.Author', blank=True, null=True)

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_voter_hash_from_email(email):
        hashed = hashlib.sha1()
        hashed.update(settings.SECRET_KEY)
        hashed.update(email)
        hashed.update(str(datetime.date.today().year))
        hashed.update('Who is best p0ny?')
        return hashed.hexdigest()

    @classmethod
    def check_and_get_voter(cls, email, hash):
        control_hash = cls.get_voter_hash_from_email(email)
        if control_hash == hash:
            try:
                return cls.objects.get(email=email)
            except cls.DoesNotExist:
                pass
        return None

    def get_voter_link(self):
        hashed = self.get_voter_hash_from_email(self.email)
        return "%s://kalendar.%s%s" % (
            settings.SITE_PROTOCOL,
            settings.SITE_DOMAIN,
            reverse('voting_vote', args=(self.email, hashed))
        )


class Month:
    INTRO = 0
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUN = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12
    CHOICES = (
        (INTRO, 'úvod'),
        (JANUARY, 'leden'),
        (FEBRUARY, 'únor'),
        (MARCH, 'březen'),
        (APRIL, 'duben'),
        (MAY, 'květen'),
        (JUN, 'červen'),
        (JULY, 'červenec'),
        (AUGUST, 'srpen'),
        (SEPTEMBER, 'září'),
        (OCTOBER, 'říjen'),
        (NOVEMBER, 'listopad'),
        (DECEMBER, 'prosinec'),
    )

    @classmethod
    def get(cls, month):
        return dict(cls.CHOICES).get(month, None)


class Season:
    INTRO = 'intro'
    SPRING = 'spring'
    SUMMER = 'summer'
    AUTUMN = 'autumn'
    WINTER = 'winter'
    CHOICES = (
        (INTRO, 'úvod'),
        (SPRING, 'měsíce'),
        #(SUMMER, 'léto'),
        #(AUTUMN, 'podzim'),
        #(WINTER, 'zima'),
    )
    CHOICES_MONTHS = (
        (INTRO, [Month.INTRO]),
        (SPRING, [Month.MARCH, Month.APRIL, Month.MAY, Month.JUN, Month.JULY, Month.AUGUST, Month.SEPTEMBER, Month.OCTOBER, Month.NOVEMBER, Month.DECEMBER, Month.JANUARY, Month.FEBRUARY]),
        #(SUMMER, [Month.JUN, Month.JULY, Month.AUGUST]),
        #(AUTUMN, [Month.SEPTEMBER, Month.OCTOBER, Month.NOVEMBER]),
        #(WINTER, [Month.DECEMBER, Month.JANUARY, Month.FEBRUARY]),
    )

    @classmethod
    def get(cls, season):
        return dict(cls.CHOICES).get(season, None)

    @classmethod
    def months_dict(cls):
        res = {}
        for season, months in cls.CHOICES_MONTHS:
            res[season] = OrderedDict()
            for m in months:
                res[season][m] = Month.get(m)
        return res


class VotedImageManager(BaseVotingManager):
    pass


class VotedImage(models.Model):
    date_created = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='voted_images/')
    season = models.CharField(max_length=6, choices=Season.CHOICES)

    authors = models.ManyToManyField('calendareshop.Author', related_name='images')

    objects = VotedImageManager()

    def __unicode__(self):
        return u'%s' % self.image.name


class VoteManager(BaseVotingManager):
    pass


class Vote(models.Model):
    date_created = models.DateTimeField(auto_now=True)
    season = models.CharField(max_length=6, choices=Season.CHOICES)
    month = models.PositiveIntegerField(choices=Month.CHOICES)

    image = models.ForeignKey(VotedImage, related_name='votes')
    voter = models.ForeignKey(Voter, related_name='votes')

    objects = VoteManager()

    def __unicode__(self):
        return u"Vote from %s for %s" % (self.voter, self.image)

    @staticmethod
    def voting_ended():
        end = datetime.date(datetime.datetime.now().year, *settings.VOTING_END_MONTH_DAY)
        return datetime.date.today() > end
