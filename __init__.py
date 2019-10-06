#!/usr/bin/env python3

# Copyright (C) 2016 - 2019 Sylvia van Os <sylvia@hackerchick.me>
#
# Pext pass module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gettext
import html
import platform
import shutil
import re
import os
from datetime import datetime
from os.path import expanduser, normcase

from babel.dates import format_datetime

import pypass
import pyotp

from pext_base import ModuleBase
from pext_helpers import Action, SelectionType

class Module(ModuleBase):
    def init(self, settings, q):
        if platform.system() == 'Darwin':
            # Explicitly add support for MacGPG2
            os.environ['PATH'] = os.environ['PATH'] + ':/usr/local/MacGPG2/bin'

        try:
            lang = gettext.translation('pext_module_pass', localedir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locale'), languages=[settings['_locale']])
        except FileNotFoundError:
            lang = gettext.NullTranslations()
            print("No {} translation available for pext_module_pass".format(settings['_locale']))

        lang.install()

        self.data_location = expanduser(normcase("~/.password-store/")) if ('directory' not in settings) else expanduser(normcase(settings['directory']))
        self.password_store = pypass.PasswordStore(self.data_location)

        self.q = q
        self.settings = settings

        if self.settings['_api_version'] < [0, 11, 1]:
            self.q.put([Action.critical_error, _("This module requires at least API version 0.11.1, you are using {}. Please update Pext.").format(".".join([str(i) for i in self.settings['_api_version']]))])
            return

        self.ANSIEscapeRegex = re.compile('(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
        self.passwordEntries = {}

        self.q.put([Action.set_base_context, [_("Create"), _("Generate")]])

        self._get_entries()

        if not os.path.join(self.data_location, ".gpg-id"):
            self._init()

    def _get_data_location(self):
        return self.data_location

    def _get_entries(self):
        for password in sorted(self.password_store.get_passwords_list(), key=lambda name: os.path.getatime("{}.gpg".format(name)), reverse=True):
            entry_path = "{}.gpg".format(password)
            entry = password[len(self._get_data_location()):]

            self.q.put([Action.add_entry, entry])
            self.q.put([Action.set_entry_info, entry, _("<b>{}</b><br/><br/><b>Last opened</b><br/>{}<br/><br/><b>Last modified</b><br/>{}").format(html.escape(entry), format_datetime(datetime.fromtimestamp(os.path.getatime(entry_path)).replace(microsecond=0), locale=self.settings['_locale']), format_datetime(datetime.fromtimestamp(os.path.getmtime(entry_path)).replace(microsecond=0), locale=self.settings['_locale']))])
            if self.settings['_api_version'] < [0, 12, 0]:
                self.q.put([Action.set_entry_context, entry, [_("Open"), _("Edit"), _("Copy"), _("Rename"), _("Remove")]])
            else:
                self.q.put([Action.set_entry_context, entry, [_("Open"), _("Edit"), _("Copy"), _("Rename"), _("Add OTP")]])

    def process_response(self, response, identifier):
        # User cancellation
        if response is None:
            return

        data = identifier.split()
        if data[0] == "add_otp":
            if len(data) == 1:
                if response is not None:
                    self._add_otp(name=response)
                else:
                    self._add_otp()
            else:
                if response is not None:
                    if data[-1] in ["TOTP", "HOTP"]:
                        self._add_otp(name=" ".join(data[1:-1]), otp_type=data[-1], secret=response)
                    else:
                        self._add_otp(name=" ".join(data[1:]), otp_type=response)
                else:
                    if data[-1] in ["TOTP", "HOTP"]:
                        self._add_otp(name=" ".join(data[1:-1], otp_type=data[-1]))
                    else:
                        self._add_otp(name=" ".join(data[1:]))
        elif data[0] == "copy":
            if len(data) == 1:
                if response is not None:
                    self._copy(name=response)
                else:
                    self._copy()
            else:
                if response is not None:
                    self._copy(name=" ".join(data[1:]), copy_name=response)
                else:
                    self._copy(name=" ".join(data[1:]))
        elif data[0] == "edit":
            if len(data) == 1:
                if response is not None:
                    self._edit(name=response)
                else:
                    self._edit()
            else:
                if response is not None:
                    self._edit(name=" ".join(data[1:]), value=response)
                else:
                    self._edit(name=" ".join(data[1:]))
        elif data[0] == "generate":
            if len(data) == 1:
                if response is not None:
                    self._generate(name=response)
                else:
                    self._generate()
            else:
                if response is not None:
                    self._generate(name=" ".join(data[1:]), length=response if response else 15)
                else:
                    self._generate(name=" ".join(data[1:]))
        elif data[0] == "init":
            if response is not None:
                self._init(gpg_id=response)
            else:
                self._init()
        elif data[0] == "insert":
            if len(data) == 1:
                if response is not None:
                    self._insert(name=response)
                else:
                    self._insert()
            else:
                if response is not None:
                    self._insert(name=" ".join(data[1:]), value=response)
                else:
                    self._insert(name=" ".join(data[1:]))
        elif data[0] == "remove":
            if len(data) == 1:
                if response is not None:
                    self._remove(name=response)
                else:
                    self._remove()
            else:
                if response is not None:
                    self._remove(name=" ".join(data[1:]), confirmed=response)
                else:
                    self._remove(name=" ".join(data[1:]))
        elif data[0] == "rename":
            if len(data) == 1:
                if response is not None:
                    self._rename(name=response)
                else:
                    self._rename()
            else:
                if response is not None:
                    self._rename(name=" ".join(data[1:]), new_name=response)
                else:
                    self._rename(name=" ".join(data[1:]))
        else:
            self.q.put([Action.critical_error, _("Unknown request received: {}").format(" ".join(data))])

    def _add_otp(self, name=None, otp_type=None, secret=None):
        if not name:
            self.q.put([Action.ask_input, _("Add OTP to which password?"), "", "add_otp"])
        elif not otp_type:
            self.q.put([Action.ask_choice, _("Use which OTP type?"), ["TOTP", "HOTP"], "add_otp {}".format(name)])
        elif not secret:
            self.q.put([Action.ask_input, _("What is the OTP secret?"), "", "add_otp {} {}".format(name, otp_type)])
        else:
            if otp_type == "TOTP":
                otp_uri = pyotp.TOTP(secret).provisioning_uri()
            elif otp_type == "HOTP":
                otp_uri = pyotp.HOTP(secret).provisioning_uri()
            else:
                return

            current_data = self.password_store.get_decrypted_password(name)
            self.password_store.insert_password(name, "{}\n{}".format(current_data, otp_uri))

    def _copy(self, name=None, copy_name=None):
        if not name:
            self.q.put([Action.ask_input, _("Copy which password?"), "", "copy"])
        elif not copy_name:
            self.q.put([Action.ask_input, _("What should the copy of {} be named?").format(name), name, "copy {}".format(name)])
        else:
            try:
                shutil.copyfile(
                    os.path.join(self._get_data_location(), "{}.gpg".format(name)),
                    os.path.join(self._get_data_location(), "{}.gpg".format(copy_name))
                )
            except shutil.SameFileError:
                self.q.put([Action.ask_input, _("What should the copy of {} be named?").format(name), name, "copy {}".format(name)])
                return

            self.q.put([Action.set_selection, []])

    def _edit(self, name=None, value=None):
        if not name:
            self.q.put([Action.ask_input, _("What is the name of the password to edit?"), "", "edit"])
        elif not value:
            current_data = self.password_store.get_decrypted_password(name)
            self.q.put([Action.ask_input_multi_line, _("What should the value of {} be?").format(name), current_data, "edit {}".format(name)])
        else:
            self.password_store.insert_password(name, value)
            self.q.put([Action.set_selection, []])

    def _generate(self, name=None, length=None):
        if not name:
            self.q.put([Action.ask_input, _("Generate a random password under which name?"), "", 'generate'])
        elif not length:
            self.q.put([Action.ask_input, _("How many characters long should the password be?"), "15", "generate {}".format(name)])
        else:
            password = self.password_store.generate_password(name, length=int(length))
            self._insert(name=name, value=password)

    def _init(self, gpg_id=None):
        if not gpg_id:
            self.q.put([Action.ask_input, _("Please provide a GPG ID to initialize this directory with."), "", "init"])
        else:
            self.password_store.init(gpg_id, self._get_data_location)
            self.q.put([Action.set_selection, []])

    def _insert(self, name=None, value=None):
        if not name:
            self.q.put([Action.ask_input, _("What is the name of the password?"), "", 'insert'])
        elif not value:
            self.q.put([Action.ask_input_multi_line, _("What should the value of {} be?").format(name), "", "insert {}".format(name)])
        else:
            self.password_store.insert_password(name, value)
            self.q.put([Action.set_selection, []])

    def _remove(self, name=None, confirmed=None):
        if not name:
            self.q.put([Action.ask_input, _("Remove which password?"), "", "remove"])
        elif confirmed is None:
            self.q.put([Action.ask_question, _("Are you sure you want to remove {}?").format(name), "remove {}".format(name)])
        elif not confirmed:
            return
        else:
            os.remove(
                os.path.join(self._get_data_location(), "{}.gpg".format(name)),
            )
            self.q.put([Action.set_selection, []])

    def _rename(self, name=None, new_name=None):
        if not name:
            self.q.put([Action.ask_input, _("Rename which password?"), "", "rename"])
        elif not new_name:
            self.q.put([Action.ask_input, _("What should the new name of {} be?").format(name), name, "rename {}".format(name)])
        else:
            os.rename(
                os.path.join(self._get_data_location(), "{}.gpg".format(name)),
                os.path.join(self._get_data_location(), "{}.gpg".format(new_name))
            )
            self.q.put([Action.set_selection, []])

    def selection_made(self, selection):
        if len(selection) == 0:
            # We're at the main menu
            self.passwordEntries = {}
            self.q.put([Action.set_header])
            self.q.put([Action.replace_command_list, []])
            self.q.put([Action.replace_entry_list, []])
            self._get_entries()
        elif selection[-1]["type"] == SelectionType.none:
            # Global context menu option
            if selection[-1]["context_option"] == _("Create"):
                self.q.put([Action.set_selection, []])
                self._insert()
                return
            elif selection[-1]["context_option"] == _("Generate"):
                self.q.put([Action.set_selection, []])
                self._generate()
                return
            else:
                self.q.put([Action.critical_error, _("Unexpected selection_made value: {}").format(selection)])
        elif len(selection) == 1:
            if selection[0]["type"] == SelectionType.entry:
                if selection[0]["context_option"] == _("Edit"):
                    self.q.put([Action.set_selection, []])
                    self._edit(name=selection[0]["value"])
                    return
                elif selection[0]["context_option"] == _("Copy"):
                    self.q.put([Action.set_selection, []])
                    self._copy(name=selection[0]["value"])
                    return
                elif selection[0]["context_option"] == _("Rename"):
                    self.q.put([Action.set_selection, []])
                    self._rename(name=selection[0]["value"])
                    return
                elif selection[0]["context_option"] == _("Remove"):
                    self.q.put([Action.set_selection, []])
                    self._remove(selection[0]["value"])
                    return
                elif selection[0]["context_option"] == _("Add OTP"):
                    self.q.put([Action.set_selection, []])
                    self._add_otp(selection[0]["value"])
                    return

                results = self.password_store.get_decrypted_password(selection[0]["value"])
                if results is None:
                    self.q.put([Action.set_selection, []])
                    return

                self.q.put([Action.replace_entry_list, []])
                self.q.put([Action.replace_command_list, []])

                result_lines = results.rstrip().splitlines()

                # Parse OTP
                for number, line in enumerate(result_lines):
                    try:
                        otp = pyotp.parse_uri(line)
                    except ValueError:
                        continue

                    if isinstance(otp, pyotp.TOTP):
                        otp_code = otp.now()
                    else:
                        otp_code = otp.generate_otp()

                    result_lines[number] = "OTP: {}".format(otp_code)

                # If only a password and no other fields, select password immediately
                if len(result_lines) == 1:
                    self.q.put([Action.copy_to_clipboard, result_lines[0]])
                    self.q.put([Action.close])
                    return

                for line in result_lines:
                    if len(self.passwordEntries) == 0:
                        self.passwordEntries["********"] = line
                        self.q.put([Action.add_entry, "********"])
                    else:
                        self.passwordEntries[line] = line
                        self.q.put([Action.add_entry, line])
            else:
                self.q.put([Action.critical_error, _("Unexpected selection_made value: {}").format(selection)])
        elif len(selection) == 2:
            # We're selecting a password
            if selection[1]["value"] == "********":
                self.q.put([Action.copy_to_clipboard, self.passwordEntries["********"]])
            else:
                # Get the final part to prepare for copying. For example, if
                # the entry is named URL: https://example.org/", only copy
                # "https://example.org/" to the clipboard
                copyStringParts = self.passwordEntries[selection[1]["value"]].split(": ", 1)

                copyString = copyStringParts[1] if len(copyStringParts) > 1 else copyStringParts[0]
                self.q.put([Action.copy_to_clipboard, copyString])

            self.passwordEntries = {}
            self.q.put([Action.close])
        else:
            self.q.put([Action.critical_error, _("Unexpected selection_made value: {}").format(selection)])
