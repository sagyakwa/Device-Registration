import configparser
import os
import re
import sys
from datetime import datetime
from os.path import join, dirname, abspath

import yaml
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QRunnable, QSize, QThreadPool
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QSplashScreen, QPushButton, QLineEdit
from PyQt5 import QtGui
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
    def __init__(self, username, mac_address, device_type, sponsor):
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
        self.options = Options()
        self.options.headless = True  # True to make headless, False to make browser visible

    def run(self):
        # Make dictionary to check whether format of text boxes are correct
        global everything
        everything = {
            'right_address': bool(self.check_mac_address(self.mac_address)),
            'right_username': bool(self.check_username(self.username)),
            'right_name': bool(self.check_sponsor(self.sponsor))
        }

        # Check to see that there is some text in the Text boxes and it is correctly formatted
        if all(everything.values()):
            self.signals.disable_widgets_signal.emit(True)
            self.browser = webdriver.Chrome(options=self.options)
            # go to the homepage
            self.signals.label_update_signal.emit("Starting...")
            self.browser.get('http://fsunac-1.framingham.edu/administration')
            self.login()
            try:
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
                    self.signals.popup_signal.emit('Congratulations', f'User {self.username} has been '
                    f'registered\nwith the following '
                    f'MAC Address: {self.mac_address}')
                    self.signals.label_update_signal.emit("Ready")
            except TimeoutException:
                self.signals.popup_signal.emit('Errors in yout form', 'Check your internet connect \n and make sure '
                                                                      'you are connected to FSU\'s network')
        else:
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
            self.signals.disable_widgets_signal(False)
            self.signals.popup_signal.emit('Errors in your form', msg)

    # Check to see if mac address is valid format eg. (00:00:00:00:00:000 or (00-00-00-00-00-00)
    @staticmethod
    def check_mac_address(mac_address):
        return bool(re.match('[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$', mac_address.lower()))

    # Check to see if username is correct format eg. (teststudent) or (teststudent45) but not (test student)
    @staticmethod
    def check_username(username):
        return bool(re.match(r'[a-zA-Z]{1,}', username.lower()) or (
                re.match(r'[a-zA-Z]{1,}', username.lower()) and username.endswith(re.match(r'[0-9]{1,}'))))

    @staticmethod
    def check_sponsor(your_name):
        return bool(re.match(r'[a-zA-Z]{1,}(.*[\s]?)', your_name.lower()))

    def find_and_send_keys(self, xpath, keys_to_send):
        textbox = WebDriverWait(self.browser, 10).until(
            ec.presence_of_element_located(
                (By.XPATH, xpath))
        )

        # self.browser.execute_script(f'arguments[0].value={keys_to_send}', textbox)
        textbox.send_keys(keys_to_send)

    def find_and_click(self, xpath):
        clickable_object = WebDriverWait(self.browser, 10).until(
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
        try:
            self.find_and_send_keys(username_xpath, self.login_username)

            self.find_and_send_keys(password_xpath, self.login_password)

            login_button = WebDriverWait(self.browser, 6).until(
                ec.presence_of_element_located(
                    (By.XPATH, login_button_xpath))
            )
            login_button.click()
            self.browser.refresh()
        except NoSuchElementException:
            self.signals.popup_signal.emit("Error", "Unable to login. Check your internet connection")
        except TimeoutException:
            self.signals.popup_signal.emit("Error", "Unable to login. Check your internet connection")

    def find_user(self):
        users_button_xpath = '//*[@id="topMenuBar"]/ul/li[2]/a'
        filter_bar_xpath = '//*[@id="registrationTableForm"]/div[2]/input[1]'
        search_button_xpath = '//*[@id="registrationTableForm"]/div[2]/input[2]'
        user_checkbox_xpath = '//*[@id="adminUserTable"]/tbody/tr/td[1]/input'
        self.find_and_click(users_button_xpath)
        self.find_and_send_keys(filter_bar_xpath, self.username)
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
        self.find_and_send_keys(username_textbox, self.username)
        self.find_and_send_keys(email_textbox, f"{self.username}@student.framingham/edu")
        self.find_and_send_keys(start_time_textbox, registration_start_date)
        self.find_and_send_keys(expires_time_textbox, registration_end_date)
        self.find_and_send_keys(sponsor_textbox, self.sponsor)
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
        self.username = None
        self.mac_address = None
        self.device_type = None
        self.sponsor = None

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
                        self.ui.change_mode.setIconSize(QSize(28, 28))
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
        # self.ui.sponsor_textbox.clear()

    def change_ui(self):
        with open(_config, 'r'):
            if self.config.getboolean('Default', 'dark_mode'):
                styles.light_mode(QApplication.instance())
                self.ui.change_mode.setIcon(self.dark_mode_icon)
                self.ui.change_mode.setIconSize(QSize(23, 23))
                self.ui.change_mode.setToolTip("<i><b>Dark Mode</b></i>")
                with open(_config, 'w') as config:
                    self.config['Default']['dark_mode'] = 'false'
                    self.config.write(config)
            else:
                styles.dark_mode(QApplication.instance())
                self.ui.change_mode.setIcon(self.light_mode_icon)
                self.ui.change_mode.setIconSize(QSize(42, 42))
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
    def on_pushButton_clicked(self):
        # Get the texts entered in the textbox and pass them to the thread
        self.username = self.ui.username_textbox.text()
        self.mac_address = self.ui.mac_textbox.text()
        self.device_type = self.ui.device_textbox.text()
        self.sponsor = self.ui.sponsor_textbox.text()

        registration_thread = RegisterThread(self.username, self.mac_address, self.device_type, self.sponsor)
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
