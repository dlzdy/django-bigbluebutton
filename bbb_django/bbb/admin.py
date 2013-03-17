# coding: utf-8
import re
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import ugettext_lazy as _
from django import forms

from bbb.models import Meeting,UserProfile

class MeetingForm(forms.ModelForm):
    agenda = forms.CharField(label=_('agenda'), widget=forms.Textarea)
    class Meta:
        model = Meeting

class MeetingAdmin(admin.ModelAdmin):
    list_display = ('name','id') 
    list_filter = ['name', 'user']
    search_fields = ['name','user' ]
    form = MeetingForm

admin.site.register(Meeting, MeetingAdmin)

"""
This code aims to override the username's regex of the Django admin panel to be
able to allow unicode usernames.

Just add this code to an app as admin.py and everything will be done.
"""

help_text = _("Required. 30 characters or fewer. Unicode alphanumeric "
              "characters only (letters, digits and underscores).")

error_message = _("This value must contain only unicode letters, "
                  "numbers and underscores.")


class UnicodeRegexField(forms.RegexField):
    """
    Return a regex field that allows unicode chars.

    The ``regex`` parameter needs to be a basestring for that to happen.
    """
    def __init__(self, regex, max_length=None, min_length=None, 
        error_message=None, *args, **kwargs):

        if isinstance(regex, basestring):
            # Here it's the trick
            regex = re.compile(regex, re.UNICODE)

        super(UnicodeRegexField, self).__init__(regex, max_length, 
            min_length, *args, **kwargs)


class UserCreationForm(UserCreationForm):
    # The regex must be a string
    username = UnicodeRegexField(label=_("Username"), max_length=30,
        regex=u'^\w+$', help_text=help_text, error_message=error_message)


class UserChangeForm(UserChangeForm):
    # The regex must be a string
    username = UnicodeRegexField(label=_("Username"), max_length=30,
        regex=u'^\w+$', help_text=help_text, error_message=error_message)

class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False

class UserProfileAdmin(UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    inlines = (ProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserProfileAdmin) 
