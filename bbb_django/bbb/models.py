from django.db import models
from django import forms
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin import widgets
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models.signals import pre_delete,post_save

from urllib2 import urlopen
from urllib import urlencode
from hashlib import sha1
import xml.etree.ElementTree as ET
import random
import datetime
import pytz

from django.core.validators import validate_email

class MultiEmailField(forms.Field):
    def to_python(self, value):
        "Normalize data to a list of strings."

        # Return an empty list if no input was given.
        if not value:
            return []
        return value.split(',')

    def validate(self, value):
        "Check if value consists only of valid emails."

        # Use the parent's handling of required fields, etc.
        super(MultiEmailField, self).validate(value)

        for email in value:
            validate_email(email)

def parse(response):
    settings.LOGGER.debug(response)
    try:
        xml = ET.XML(response)
        code = xml.find('returncode').text
        if code == 'SUCCESS':
            return xml
        else:
            raise
    except:
        return None

MEETING_DURATION = (
    (0, _('unlimited')),
    (15, _('15 min')),
    (30, _('30 min')),
    (60, _('1 hour')),
    (120, _('2 hour')),
    (180, _('3 hour')),
)

def tz_convert(dt, from_tz, to_tz):
    src_tz = pytz.timezone(from_tz)
    dst_tz = pytz.timezone(to_tz)
    if src_tz is not None:
        dt = src_tz.localize(dt)
    if dst_tz is not None:
        dt = dt.astimezone(dst_tz)
    return dt

TIME_ZONES = (
    (tz, tz) for tz in pytz.common_timezones
)

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    tz = models.CharField(max_length=100, default='Asia/Shanghai', choices=TIME_ZONES, verbose_name=_('timezone'))

def create_user_profile(sender, instance, created, **kwargs):  
    if created:  
       profile, created = UserProfile.objects.get_or_create(user=instance)  

post_save.connect(create_user_profile, sender=User) 


class Meeting(models.Model):

    user = models.ForeignKey(User, verbose_name=_('user'))
    name = models.CharField(max_length=100, verbose_name=_('meeting name'))
    attendee_password = models.CharField(max_length=50, verbose_name=_('attendee password'))
    moderator_password = models.CharField(max_length=50, verbose_name=_('moderator password'))
    #welcome = models.CharField(max_length=100, blank=True, verbose_name=_('welcome message'))
    record = models.BooleanField(default=False, verbose_name=_('record'))
    duration = models.IntegerField(default=0, choices=MEETING_DURATION, verbose_name=_('duration'))
    start_time = models.DateTimeField(verbose_name=_('start time'))
    started = models.BooleanField(default=False, verbose_name=_('started'))
    agenda = models.CharField(max_length=1000, blank=True, verbose_name=_('agenda'))

    #def __unicode__(self):
    #    return self.name

    class Meta:
        verbose_name = _('meeting')
        verbose_name_plural = _('meetings')
        permissions = (
            ('create_meeting', 'Can create meeting'),
	    ('end_meetnig', 'Can end meeting'),
        )

    @classmethod
    def api_call(self, query, call):
        prepared = "%s%s%s" % (call, query, settings.SALT)
        checksum = sha1(prepared).hexdigest()
        result = "%s&checksum=%s" % (query, checksum)
        return result

    def is_running(self):
        call = 'isMeetingRunning'
        query = urlencode((
            ('meetingID', self.id),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        result = parse(urlopen(url).read())
        if result:
            return result.find('running').text
        else:
            return 'error'

    @classmethod
    def end_meeting(self, meeting_id, password):
        call = 'end'
        query = urlencode((
            ('meetingID', meeting_id),
            ('password', password),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        result = parse(urlopen(url).read())
        if result:
            pass
        else:
            return 'error'

    @classmethod
    def meeting_info(self, meeting_id, password):
        call = 'getMeetingInfo'
        query = urlencode((
            ('meetingID', meeting_id),
            ('password', password),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        r = parse(urlopen(url).read())
        if r:
            # Create dict of values for easy use in template
            d = {
                'start_time': r.find('startTime').text,
                'end_time': r.find('endTime').text,
                'participant_count': r.find('participantCount').text,
                'moderator_count': r.find('moderatorCount').text,
                'moderator_pw': r.find('moderatorPW').text,
                'attendee_pw': r.find('attendeePW').text,
                'invite_url': reverse('join', args=[meeting_id]),
            }
            return d
        else:
            return None

    @classmethod
    def get_meetings(self):
        call = 'getMeetings'
        query = urlencode((
            ('random', 'random'),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        result = parse(urlopen(url).read())
        if result:
            # Create dict of values for easy use in template
            d = {}
            r = result[1].findall('meeting')
            for m in r:
                meeting_name = m.find('meetingName').text
                meeting_id = m.find('meetingID').text
                password = m.find('moderatorPW').text
                d[meeting_id] = {
                    'name': meeting_name,
                    'meeting_id': meeting_id,
                    'running': m.find('running').text,
                    #'moderator_pw': password,
                    #'attendee_pw': m.find('attendeePW').text,
                    'info': Meeting.meeting_info(
                        meeting_id,
                        password)
                }
                print d
            return d
        else:
            return 'error'

    @classmethod
    def delete_recordings(self, meeting_id=None):
        """
        Delete one or more recordings for a given recordID (or set of record IDs).
        
        :param record_id: A record ID for specify the recordings to delete. It can be a set of meetingIDs separate by commas. 
        """
        record_info = Meeting.get_recordings(meeting_id)
        record_id_list = []
        for item in record_info:
            record_id_list.append(item['record_id'])

        call = 'deleteRecordings'
        if record_id_list:
            query = urlencode((
                            ('recordID', ','.join(record_id_list)),
                             ))
        else:
            query = ''
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        print 'delete recording url:%s'%url
        r = parse(urlopen(url).read())
        # ToDO implement more keys
        if r:
            return r.find('deleted').text == 'true'
        return False

    @classmethod
    def get_recordings(self, meeting_id=None):
        """
        Retrieves the recordings that are available for playback for a given meetingID (or set of meeting IDs).
        
        :param meetingID: The meeting ID that identifies the meeting 
        """
        call = 'getRecordings'
        if meeting_id:
            query = urlencode((
                           ('meetingID', meeting_id),
                           ))
        else:
            query = ''
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        print 'recording url:%s'%url
        r = parse(urlopen(url).read())
        # ToDO implement more keys
        if r:
            recordings = r.find('recordings')
            if recordings is None:
                return None
            records = []
            for session in recordings.findall('recording'):
	        record = {}
                record['record_id'] = session.find('recordID').text
                record['meeting_id'] = session.find('meetingID').text
                record['meeting_name'] = session.find('name').text
                record['published'] = session.find('published').text == "true"
                record['start_time'] = session.find('startTime').text
                record['end_time'] = session.find('endTime').text
                playbacks = session.find('playback')
                for f in playbacks.findall('format'):
                    if f.find('type').text == 'slides':
                        record['playback_url'] = f.find('url').text
                        record['length'] = f.find('length').text
                records.append(record)
            #print records
            return records
        else:
            return None

    def start(self):
        call = 'create' 
        voicebridge = 70000 + random.randint(0,9999)
        query = urlencode((
            ('name', self.name.encode('utf8')),
            ('meetingID', self.id),
            ('attendeePW', self.attendee_password),
            ('moderatorPW', self.moderator_password),
            ('voiceBridge', voicebridge),
            #('welcome', self.welcome.encode('utf8')),
            ('welcome', self.agenda.encode('utf8')),
            ('record', self.record),
            #('duration', self.duration),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        print url
        result = parse(urlopen(url).read())
        if result:
            return result
        else:
            raise

    @classmethod
    def join_url(self, meeting_id, name, password):
        call = 'join'
        query = urlencode((
            ('fullName', name.encode('utf8')),
            ('meetingID', meeting_id),
            ('password', password),
        ))
        hashed = self.api_call(query, call)
        url = settings.BBB_API_URL + call + '?' + hashed
        return url

    class CreateForm(forms.Form):
        name = forms.CharField(label=_('meeting name'))
        attendee_password = forms.CharField(label=_('attendee password'),
            widget=forms.PasswordInput(render_value=False))
        moderator_password = forms.CharField(label=_('moderator password'),
            widget=forms.PasswordInput(render_value=False))
        #welcome = forms.CharField(label=_('welcome message'), initial=_('Welcome!'))
        record = forms.BooleanField(label=_('record'), initial=False, required=False)
        duration = forms.ChoiceField(label=_('duration'), choices=MEETING_DURATION)
        start_time = forms.DateTimeField(label=_('start time'), widget=widgets.AdminSplitDateTime())
        agenda = forms.CharField(label=_('agenda'), required=False, widget=forms.Textarea)
        recipients = MultiEmailField(label=_('email recipients'), required=False)
       
        def clean(self):
            data = self.cleaned_data

            # TODO: should check for errors before modifying
            #data['meeting_id'] = data.get('name')

            #if Meeting.objects.filter(name = data.get('name')):
            #    raise forms.ValidationError("That meeting name is already in use")
            return data

    class JoinForm(forms.Form):
        name = forms.CharField(label=_("Your name"))
        password = forms.CharField(label=_('password'),
            widget=forms.PasswordInput(render_value=False))


def delete_record_cb(sender, **kwargs):
    meeting = kwargs['instance']
    if meeting.record:
        Meeting.delete_recordings(meeting.id)

pre_delete.connect(delete_record_cb, sender=Meeting)
