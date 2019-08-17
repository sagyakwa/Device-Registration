import configparser
import os
import re
import sys
import webbrowser
from datetime import datetime
from os.path import join, dirname, abspath

import yaml
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QRunnable, QSize, QThreadPool, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton, QLineEdit, QLabel
from qtpy import uic
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication, QMainWindow, QMessageBox
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

from modern_ui import styles
from modern_ui import windows

_UI = join(dirname(abspath(__file__)), 'mainwindow.ui')
_config = join(dirname(abspath(__file__)), 'config')
_about = join(dirname(abspath(__file__)), 'about')
_help = join(dirname(abspath(__file__)), 'help')


class Signals(QObject):
    label_update_signal = pyqtSignal(str)
    popup_signal = pyqtSignal(str, str)
    clear_textboxes_signal = pyqtSignal()
    disable_widgets_signal = pyqtSignal(bool)


class RegisterThread(QRunnable):
    def __init__(self, username, mac_address, device_type, sponsor, user_type='student'):
        super(RegisterThread, self).__init__()
        self.signals = Signals()
        credential_location = join(dirname(abspath(__file__)), 'credentials')
        credentials = yaml.safe_load(open(credential_location))
        self.login_username = credentials['credentials']['username']
        self.login_password = credentials['credentials']['password']
        self.username = username
        self.mac_address = mac_address
        self.device_type = device_type
        self.sponsor = sponsor
        self.user_type = user_type
        self.options = Options()
        self.options.headless = False  # True to make headless, False to make browser visible

    def run(self):
        # Make dictionary to check whether format of text boxes are correct
        global everything
        everything = {
            'right_address': bool(self.check_mac_address(self.mac_address)),
            'right_username': bool(self.check_username(self.username)),
            'right_name': bool(self.check_sponsor(self.sponsor))
        }

        if self.user_type != 'student' and self.user_type != 'faculty':
            everything.update(correct_email=bool(self.check_email(self.user_type)))
            everything.update(right_username=bool(self.check_username(self.username, other_user=True)))

        # Check to see that there is some text in the Text boxes and it is correctly formatted
        if all(everything.values()):
            self.execute()
        else:
            # if self.user_type != 'student' or self.user_type != 'faculty':
            #     everything.update(correct_email=bool(self.check_email(self.user_type)))
            # Go through the dictionary and give appropriate error messages if it turns out something is wrong
            for _ in everything:
                global msg
                msg = ''
                if not everything['right_address']:
                    msg += 'Invalid MAC address format!\n'
                    pass
                if not everything['right_username']:
                    msg += 'Invalid username!\n'
                if not everything['right_name']:
                    msg += 'You entered invalid values for your name!\n'
                try:
                    if not everything['correct_email']:
                        msg += 'Invalid email address!\n'
                except KeyError:
                    pass
            self.signals.disable_widgets_signal.emit(False)
            self.signals.popup_signal.emit('Errors in your form', msg)

    def execute(self):
        self.signals.label_update_signal.emit("Starting...")
        self.signals.disable_widgets_signal.emit(True)
        self.browser = webdriver.Chrome(options=self.options)
        # go to the homepage
        self.browser.get('http://fsunac-1.framingham.edu/administration')
        try:
            self.login()
            self.signals.label_update_signal.emit("Finding user...")
            if self.find_user():
                self.signals.label_update_signal.emit("User found")
                self.signals.label_update_signal.emit("Adding device...")
                self.add_device()
                self.signals.label_update_signal.emit("Done!")
                self.browser.quit()
                self.signals.clear_textboxes_signal.emit()
                self.signals.disable_widgets_signal.emit(False)
                self.signals.popup_signal.emit('Congratulations', f'User {self.username} has been '
                f'registered\nwith the following MAC Address: {self.mac_address}')
                self.signals.label_update_signal.emit("Ready")
            else:
                self.signals.label_update_signal.emit("User not found creating new user")
                self.create_new_user()
                self.find_user()
                self.signals.label_update_signal.emit("Adding device...")
                self.add_device()
                self.signals.label_update_signal.emit("Done!")
                self.browser.quit()
                self.signals.clear_textboxes_signal.emit()
                self.signals.disable_widgets_signal.emit(False)
                self.signals.popup_signal.emit('Congratulations', f'{self.username} has been '
                f'registered\nwith the following '
                f'MAC Address: {self.mac_address}')
                self.signals.label_update_signal.emit("Ready")
        except TimeoutException:
            self.signals.popup_signal.emit('Errors in your form', 'Check your internet connect \n and make sure '
                                                                  'you are connected to FSU\'s network')
            self.signals.label_update_signal.emit("Ready")
            self.signals.disable_widgets_signal.emit(False)
            self.browser.quit()

    # Check to see if mac address is valid format eg. (00:00:00:00:00:000 or (00-00-00-00-00-00)
    @staticmethod
    def check_mac_address(mac_address):
        return bool(re.match('[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$', mac_address))

    # Check to see if username is correct format eg. (teststudent) or (teststudent45) but not (test student)
    @staticmethod
    def check_username(username, other_user=False):
        if other_user:
            return True
        else:
            return bool(re.match(r'[a-zA-Z]{1,}', username.lower()) or (
                    re.match(r'[a-zA-Z]{1,}', username.lower()) and username.endswith(re.match(r'[0-9]{1,}'))))

    @staticmethod
    def check_sponsor(your_name):
        return bool(re.match(r'[a-zA-Z]{1,}(.*[\s]?)', your_name.lower()))

    @staticmethod
    def check_email(email):
        return bool(re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email.lower()))

    def find_and_send_keys(self, xpath, keys_to_send, seconds=7):
        textbox = WebDriverWait(self.browser, seconds).until(
            ec.presence_of_element_located(
                (By.XPATH, xpath))
        )

        # self.browser.execute_script(f'arguments[0].value={keys_to_send}', textbox)
        textbox.send_keys(keys_to_send)

    def find_and_click(self, xpath, seconds=7):
        clickable_object = WebDriverWait(self.browser, seconds).until(
            ec.presence_of_element_located(
                (By.XPATH, xpath)
            )
        )

        clickable_object.click()

    # Function to Login
    def login(self):
        username_xpath = '//*[@id="loginTable"]/tbody/tr[1]/td[2]/input'
        password_xpath = '//*[@id="loginTable"]/tbody/tr[2]/td[2]/input'
        login_button_xpath = '//*[@id="loginTable"]/tbody/tr[4]/td[2]/input'
        self.find_and_send_keys(username_xpath, self.login_username, seconds=3)

        self.find_and_send_keys(password_xpath, self.login_password, seconds=3)

        login_button = WebDriverWait(self.browser, 5).until(
            ec.presence_of_element_located(
                (By.XPATH, login_button_xpath))
        )
        login_button.click()


    def find_user(self):
        users_button_xpath = '//*[@id="topMenuBar"]/ul/li[2]/a'
        filter_bar_xpath = '//*[@id="registrationTableForm"]/div[2]/input[1]'
        search_button_xpath = '//*[@id="registrationTableForm"]/div[2]/input[2]'
        user_checkbox_xpath = '//*[@id="adminUserTable"]/tbody/tr/td[1]/input'
        self.find_and_click(users_button_xpath)
        self.find_and_send_keys(filter_bar_xpath, self.username, seconds=5)
        self.find_and_click(search_button_xpath)
        try:
            self.browser.find_element_by_xpath(user_checkbox_xpath)
        except NoSuchElementException:
            return False
        else:
            return True

    def create_new_user(self):
        current_date = datetime.now()
        registration_start_date = f'{current_date.strftime("%m/%d/%Y")} 0:00:00'
        registration_end_date = f"{current_date.strftime('%m')}/{current_date.strftime('%d')}/{int(current_date.strftime('%Y')) + 2} 0:00:00"

        users_button_xpath = '//*[@id="topMenuBar"]/ul/li[2]/a'
        first_name_textbox = '//*[@id="addEditUserTable"]/tbody/tr[1]/td[2]/input'
        last_name_textbox = '//*[@id="addEditUserTable"]/tbody/tr[3]/td[2]/input'
        add_user_button = '//*[@id="showUsersAdd"]'
        username_textbox = '//*[@id="addEditUserTable"]/tbody/tr[4]/td[2]/input'
        email_textbox = '//*[@id="addEditUserTable"]/tbody/tr[5]/td[2]/input'
        start_time_textbox = '//*[@id="regStartTime"]'
        expires_time_textbox = '//*[@id="regExpirationTime"]'
        sponsor_textbox = '//*[@id="addEditUserTable"]/tbody/tr[9]/td[2]/input'
        user_type_dropdown = '//*[@id="addEditUserTable"]/tbody/tr[10]/td[2]/select'
        submit_button = '//*[@id="addUser"]'

        self.find_and_click(users_button_xpath)
        self.find_and_click(add_user_button)
        if self.user_type == 'student':
            self.find_and_send_keys(username_textbox, self.username, seconds=3)
            self.find_and_send_keys(email_textbox, f"{self.username}@student.framingham.edu", seconds=3)
        elif self.user_type == 'faculty':
            self.find_and_send_keys(username_textbox, self.username, seconds=3)
            self.find_and_send_keys(email_textbox, f"{self.username}@framingham.edu", seconds=3)
        else:
            self.find_and_send_keys(username_textbox, self.username, seconds=3)
            name = list(self.username.split())
            try:
                self.find_and_send_keys(first_name_textbox, name[0], seconds=3)
                self.find_and_send_keys(last_name_textbox, name[1], seconds=3)
            except IndexError:
                pass
            self.find_and_send_keys(email_textbox, self.user_type, seconds=3)
        self.find_and_send_keys(start_time_textbox, registration_start_date, seconds=3)
        self.find_and_send_keys(expires_time_textbox, registration_end_date, seconds=3)
        self.find_and_send_keys(sponsor_textbox, self.sponsor, seconds=3)
        dropdown_selection = Select(self.browser.find_element_by_xpath(user_type_dropdown))
        dropdown_selection.select_by_value("Web Authentication")
        self.find_and_click(submit_button)

    def add_device(self):
        user_checkbox_xpath = '//*[@id="adminUserTable"]/tbody/tr/td[1]/input'
        register_new_device_xpath = '//*[@id="showDevicesAdd"]'
        mac_address_textbox = '//*[@id="adminRegisterDeviceTable"]/tbody/tr[2]/td[2]/input'
        group_dropdown = '//*[@id="adminRegisterDeviceTable"]/tbody/tr[3]/td[2]/select'
        description_textbox = '//*[@id="adminRegisterDeviceTable"]/tbody/tr[4]/td[2]/input'
        sponsor_textbox = '//*[@id="adminRegisterDeviceTable"]/tbody/tr[5]/td[2]/input'
        submit_button = '//*[@id="addDevice"]'

        self.find_and_click(user_checkbox_xpath)
        self.find_and_click(register_new_device_xpath)
        self.find_and_send_keys(mac_address_textbox, self.mac_address)
        dropdown_selection = Select(self.browser.find_element_by_xpath(group_dropdown))
        dropdown_selection.select_by_value("Registered Guests")
        self.find_and_send_keys(description_textbox, self.device_type)
        self.find_and_send_keys(sponsor_textbox, self.sponsor)
        self.find_and_click(submit_button)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.thread_pool = QThreadPool()
        self.ui = uic.loadUi(_UI, self)
        self.config = configparser.RawConfigParser()
        self.center()
        self.mw = windows.ModernWindow(self)
        self.dark_mode_icon = QIcon('night_mode.ico')
        self.light_mode_icon = QIcon('light_mode.ico')
        self.ui.actionAbout.triggered.connect(self.show_about)
        self.ui.actionHelp.triggered.connect(self.show_help)
        self.ui.actionAdd_user_using_website.triggered.connect(lambda: webbrowser.open_new_tab('http://fsunac-1.framingham.edu/administration'))
        self.ui.student_checkbox.stateChanged.connect(self.on_state_change)
        self.ui.faculty_checkbox.stateChanged.connect(self.on_state_change)
        self.ui.other_checkbox.stateChanged.connect(self.on_state_change)
        self.username = None
        self.mac_address = None
        self.device_type = None
        self.sponsor = None
        self.user_type = 'student'

        try:
            # Open our config file and load configs if applicable
            with open(_config, 'r') as config_file:
                if os.path.getsize(_config):
                    self.config.read_file(config_file)
                    self.ui.sponsor_textbox.setText(self.config.get('Default', 'sponsor'))
                    self.dark_mode_on = self.config.getboolean('Default', 'dark_mode')

                    if self.config.getboolean('Default', 'dark_mode'):
                        self.ui.change_mode.setIconSize(QSize(35, 35))
                        self.ui.change_mode.setIcon(self.light_mode_icon)
                        styles.dark_mode(QApplication.instance())
                        self.ui.change_mode.setToolTip("<i><b>Light Mode</b></i>")
                    else:
                        self.ui.change_mode.setIconSize(QSize(25, 25))
                        self.ui.change_mode.setIcon(self.dark_mode_icon)
                        styles.light_mode(QApplication.instance())
                        self.ui.change_mode.setToolTip("<i><b>Dark Mode</b></i>")
                else:
                    raise FileNotFoundError
        except FileNotFoundError:
            # Create config file if no config found
            self.config.add_section('Default')
            self.config['Default']['sponsor'] = ''
            self.config['Default']['dark_mode'] = 'true'
            self.ui.change_mode.setIcon(self.light_mode_icon)
            self.ui.change_mode.setIconSize(QSize(35, 35))
            self.ui.change_mode.setIcon(self.light_mode_icon)
            styles.dark_mode(QApplication.instance())
            self.ui.change_mode.setToolTip("<i><b>Light Mode</b></i>")

            with open(_config, 'w') as config_file:
                self.config.write(config_file)

        self.mw.show()

    def disable_widgets(self, bool_val):
        objects = [QPushButton, QLineEdit]
        for item in objects:
            for child in self.findChildren(item):
                if bool_val:
                    child.setEnabled(False)
                else:
                    child.setEnabled(True)

    def other_checked(self, other_checked=True):
        if other_checked:
            self.ui.username_label.setText(
                '<html><head/><body><p><span style=" color:#ff0000;">*</span>Full Name</p></body></html>')
            self.ui.progress_label.move(160, 360)
            self.ui.register_button.move(230, 330)
            self.ui.sponsor_label.setGeometry(95, 265, 151, 41)
            self.ui.sponsor_textbox.move(250, 278)

            self.email_label = QLabel('<html><head/><body><p><span style=" color:#ff0000;">*</span>User '
                                      'Email</p></body></html>', self)
            self.email_label.setStyleSheet('font: 16pt "Verdana";')
            self.email_label.setGeometry(94, 230, 151, 61)
            self.email_textbox = QLineEdit(self)
            self.email_textbox.setGeometry(250, 250, 221, 21)
            self.email_label.show()
            self.email_textbox.show()
        else:
            try:
                self.ui.username_label.setText(
                    '<html><head/><body><p><span style=" color:#ff0000;">*</span>Username</p></body></html>')
                self.email_textbox.deleteLater()
                self.email_label.deleteLater()
                self.ui.progress_label.move(160, 310)
                self.ui.register_button.move(230, 280)
                self.ui.sponsor_label.setGeometry(95, 220, 151, 41)
                self.ui.sponsor_textbox.move(250, 230)
            except AttributeError:
                pass
            except RuntimeError:
                pass

    @pyqtSlot(int)
    def on_state_change(self, state):
        if state == Qt.Checked:
            if self.sender() == self.ui.student_checkbox:
                self.other_checked(other_checked=False)
                self.user_type = 'student'
                self.ui.faculty_checkbox.setChecked(False)
                self.ui.other_checkbox.setChecked(False)
            elif self.sender() == self.ui.faculty_checkbox:
                self.other_checked(other_checked=False)
                self.user_type = 'faculty'
                self.ui.student_checkbox.setChecked(False)
                self.ui.other_checkbox.setChecked(False)
            elif self.sender() == self.ui.other_checkbox:
                self.other_checked()
                self.user_type = 'other'
                self.ui.student_checkbox.setChecked(False)
                self.ui.faculty_checkbox.setChecked(False)
        else:
            if not self.ui.student_checkbox.isChecked() and not self.ui.faculty_checkbox.isChecked() and not self.ui.other_checkbox.isChecked():
                self.ui.student_checkbox.setChecked(True)

    # Function to display an error if we get one
    def popup_msg(self, title, error_string):
        QMessageBox.about(self, title, error_string)

    # Center our application instead of putting it in the top left
    def center(self):
        frame_gm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        center_point = QApplication.desktop().screenGeometry(screen).center()
        frame_gm.moveCenter(center_point)
        self.move(frame_gm.topLeft())

    def clear_textboxes(self):
        self.ui.username_textbox.clear()
        self.ui.mac_textbox.clear()
        self.ui.device_textbox.clear()
        try:
            self.ui.email_textbox.clear()
        except RuntimeError:
            pass
        # self.ui.sponsor_textbox.clear()

    def change_ui(self):
        with open(_config, 'r'):
            if self.config.getboolean('Default', 'dark_mode'):
                styles.light_mode(QApplication.instance())
                self.ui.change_mode.setIcon(self.dark_mode_icon)
                self.ui.change_mode.setIconSize(QSize(25, 25))
                self.ui.change_mode.setToolTip("<i><b>Dark Mode</b></i>")
                with open(_config, 'w') as config:
                    self.config['Default']['dark_mode'] = 'false'
                    self.config.write(config)
            else:
                styles.dark_mode(QApplication.instance())
                self.ui.change_mode.setIcon(self.light_mode_icon)
                self.ui.change_mode.setIconSize(QSize(35, 35))
                self.ui.change_mode.setToolTip("<i><b>Light Mode</b></i>")
                with open(_config, 'w') as config:
                    self.config['Default']['dark_mode'] = 'true'
                    self.config.write(config)

    def show_about(self):
        with open(_about, 'r') as about:
            self.popup_msg('About', about.read())

    def show_help(self):
        with open(_help, 'r') as about:
            self.popup_msg('Help', about.read())

    def update_label(self, label_text):
        self.ui.progress_label.setText(label_text)

    @Slot()
    def on_change_mode_clicked(self):
        self.change_ui()

    def play_splash(self):
        pass
        # splash_pix = QPixmap('img-test.jpg')
        # splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
        # splash.setMask(splash_pix.mask())
        # splash.show()
        # app.processEvents()
        #
        # splash.finish(self)

    # When the button is clicked
    @Slot()
    def on_register_button_clicked(self):
        # Get the texts entered in the textbox and pass them to the thread
        self.username = self.ui.username_textbox.text()
        self.mac_address = self.ui.mac_textbox.text()
        self.device_type = self.ui.device_textbox.text()
        self.sponsor = self.ui.sponsor_textbox.text()

        if self.user_type == 'other':
            registration_thread = RegisterThread(self.username, self.mac_address, self.device_type, self.sponsor, user_type=self.email_textbox.text())
        else:
            registration_thread = RegisterThread(self.username, self.mac_address, self.device_type, self.sponsor, user_type=self.user_type)
        registration_thread.signals.clear_textboxes_signal.connect(self.clear_textboxes)
        registration_thread.signals.disable_widgets_signal.connect(self.disable_widgets)
        registration_thread.signals.popup_signal.connect(self.popup_msg)
        registration_thread.signals.label_update_signal.connect(self.update_label)

        self.thread_pool.start(registration_thread)

    # If the user clicks the red button to exit the window
    @Slot()
    def closeEvent(self, event):
        with open(_config, 'r'):
            self.config['Default']['sponsor'] = self.ui.sponsor_textbox.text()
        with open(_config, 'w') as config:
            self.config.write(config)
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    sys.exit(app.exec_())
