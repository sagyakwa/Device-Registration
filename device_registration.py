import configparser
import os
import re
import sys
import webbrowser
from datetime import datetime
from os.path import join, dirname, abspath

import yaml
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QRunnable, QSize, QThreadPool, pyqtSlot
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtWidgets import QPushButton, QLineEdit, QLabel, QCheckBox, QGraphicsBlurEffect, \
	QMenu, QMenuBar
from qtpy import uic
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication, QMainWindow, QMessageBox
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from modern_ui import styles
from modern_ui import windows


def resource_path(relative_path):
	if getattr(sys, 'frozen', False):
		path_type = os.path.dirname(sys.executable)
		return os.path.join(path_type, relative_path)
	else:
		path_type = os.path.dirname(__file__)
		return os.path.join(path_type, relative_path)


_UI = resource_path('mainwindow.ui')
_gif = resource_path('cube.gif')
_logo = resource_path('purple_flame.svg')
_config = resource_path('config')
_about = resource_path('about')
_help = resource_path('help')
_chrome_driver = resource_path('chromedriver.exe')


class Signals(QObject):
	label_update_signal = pyqtSignal(str)
	popup_signal = pyqtSignal(str, str)
	clear_textboxes_signal = pyqtSignal()
	disable_widgets_signal = pyqtSignal(bool)
	play_splash_signal = pyqtSignal(bool)
	set_button_clicked_signal = pyqtSignal(bool)


class RegisterThread(QRunnable):
	browser: WebDriver

	def __init__(self, username: object, mac_address: object, device_type: object, sponsor: object, user_type: object = 'student') -> object:
		super(RegisterThread, self).__init__()
		self.signals = Signals()
		credential_location = resource_path('credentials')
		credentials = yaml.safe_load(open(credential_location))
		self.login_username = credentials['credentials']['username']
		self.login_password = credentials['credentials']['password']
		self.username = username
		self.mac_address = mac_address
		self.device_type = device_type
		self.sponsor = sponsor
		self.user_type = user_type
		self.options = Options()
		self.options.headless = True  # True to make headless, False to make browser visible

	def run(self):
		# Make dictionary to check whether format of text boxes are correct
		# global everything
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
			self.start_execute()
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
			self.signals.set_button_clicked_signal.emit(False)

	def start_execute(self):
		self.signals.play_splash_signal.emit(True)
		self.signals.label_update_signal.emit("Starting...")
		self.signals.disable_widgets_signal.emit(True)
		self.browser = webdriver.Chrome(_chrome_driver, options=self.options)
		self.signals.label_update_signal.emit("Hol' up...")
		# go to the homepage
		self.browser.get('http://fsunac-1.framingham.edu/administration')

		def execute():
			self.signals.label_update_signal.emit("Adding device...")
			self.add_device()
			self.signals.label_update_signal.emit("Done!")
			self.browser.quit()
			self.signals.play_splash_signal.emit(False)
			self.signals.set_button_clicked_signal.emit(False)
			self.signals.clear_textboxes_signal.emit()
			self.signals.disable_widgets_signal.emit(False)
			self.signals.popup_signal.emit('Congratulations', f'{self.username} has been '
											f'registered\nwith {self.mac_address}')
			self.signals.label_update_signal.emit("Ready")

		try:
			self.login()
			self.signals.label_update_signal.emit("Finding user...")
			if self.find_user():
				self.signals.label_update_signal.emit("User found")
				execute()
			else:
				self.signals.label_update_signal.emit(f"{self.username} not found creating new user")
				self.create_new_user()
				self.find_user()
				execute()
		except TimeoutException:
			self.signals.play_splash_signal.emit(False)
			self.signals.popup_signal.emit("Can't connect to the network", "Check your internet connect \n and make "
																			"sure you are connected to FSU's network")
			self.signals.label_update_signal.emit("Ready")
			self.signals.disable_widgets_signal.emit(False)
			self.browser.quit()
			self.signals.set_button_clicked_signal.emit(False)

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
		registration_end_date = f"{current_date.strftime('%m')}/{current_date.strftime('%d')}/{int(current_date.strftime('%Y')) + 2} 0:00:00 "

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
	registration_thread: RegisterThread
	sponsor: object
	device_type: object
	mac_address: object
	username: object
	movie: QMovie
	gif_label: QLabel
	email_label: QLabel
	email_textbox: QLineEdit
	button_clicked: bool
	user_type: str
	light_mode_icon: QIcon
	dark_mode_icon: QIcon

	def __init__(self):
		super(MainWindow, self).__init__()
		self.thread_pool = QThreadPool()
		self.ui = uic.loadUi(_UI, self)
		self.config = configparser.RawConfigParser()
		self.center()
		self.mw = windows.ModernWindow(self)
		self.initUI()
		self.init_config()

	def initUI(self):
		self.setWindowIcon(QIcon(_logo))
		self.dark_mode_icon = QIcon('night_mode.ico')
		self.light_mode_icon = QIcon('light_mode.ico')
		self.ui.actionAbout.triggered.connect(self.show_about)
		self.ui.actionHelp.triggered.connect(self.show_help)
		self.ui.actionAdd_user_using_website.triggered.connect(
			lambda: webbrowser.open_new_tab('http://fsunac-1.framingham.edu/administration'))
		self.ui.student_checkbox.stateChanged.connect(self.on_state_change)
		self.ui.faculty_checkbox.stateChanged.connect(self.on_state_change)
		self.ui.other_checkbox.stateChanged.connect(self.on_state_change)
		self.user_type = 'student'
		self.button_clicked = False
		self.mw.show()

	def init_config(self):
		try:
			# Open our config file and load configs if applicable
			with open(_config, 'r') as config_file:
				if os.path.getsize(_config):
					self.config.read_file(config_file)
					self.ui.sponsor_textbox.setText(self.config.get('Default', 'sponsor'))

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

	def disable_widgets(self, bool_val):
		objects = [QPushButton, QLineEdit, QMenu, QMenuBar]
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
			self.ui.progress_label.move(10, 355)
			self.ui.register_button.move(230, 320)
			self.ui.sponsor_label.setGeometry(95, 265, 151, 41)
			self.ui.sponsor_textbox.move(250, 278)

			self.email_label = QLabel('<html><head/><body><p><span style=" color:#ff0000;">*</span>User '
										'Email</p></body></html>', self)
			self.email_label.setStyleSheet('font: 16pt "Verdana";')
			self.email_label.setGeometry(94, 230, 151, 61)
			self.email_textbox = QLineEdit(self)
			self.email_textbox.setGeometry(250, 250, 221, 21)
			self.email_textbox.setStyleSheet('font: 11pt "Verdana";')
			self.setTabOrder(self.ui.device_textbox, self.ui.email_textbox)
			self.ui.email_textbox.returnPressed.connect(lambda: self.ui.register_button.animateClick())
			self.email_label.show()
			self.email_textbox.show()
		else:
			try:
				self.ui.username_label.setText(
					'<html><head/><body><p><span style=" color:#ff0000;">*</span>Username</p></body></html>')
				self.email_textbox.deleteLater()
				self.email_label.deleteLater()
				self.ui.progress_label.move(10, 330)
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

	def set_button_clicked(self, bool_val):
		if bool_val:
			self.button_clicked = True
		else:
			self.button_clicked = False

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
		except RuntimeError as r:
			pass
		except AttributeError as a:
			pass

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

	def play_splash(self, bool_val):

		def blur_objects(blur=True):
			objects = [QLabel, QPushButton, QLineEdit, QCheckBox, QMenu, QMenuBar]

			for item in objects:
				for child in self.findChildren(item):
					if child is not self.ui.progress_label and child is not self.gif_label:
						if blur:
							child.setGraphicsEffect(QGraphicsBlurEffect())
						else:
							child.setGraphicsEffect(QGraphicsBlurEffect().setBlurRadius(0))

		if bool_val:
			self.gif_label = QLabel(self)
			self.gif_label.setScaledContents(True)
			self.gif_label.setGeometry(140, 20, 301, 307)
			self.movie = QMovie(_gif)
			self.gif_label.setMovie(self.movie)
			blur_objects(blur=True)
			self.gif_label.show()
			self.movie.start()
		else:
			blur_objects(blur=False)
			self.movie.stop()
			self.movie.deleteLater()
			self.gif_label.deleteLater()

	@Slot()
	def on_register_button_clicked(self):
		self.button_clicked = True
		# Get the texts entered in the textbox and pass them to the thread
		self.username = self.ui.username_textbox.text()
		self.mac_address = self.ui.mac_textbox.text()
		self.device_type = self.ui.device_textbox.text()
		self.sponsor = self.ui.sponsor_textbox.text()

		if self.user_type == 'other':
			self.registration_thread = RegisterThread(self.username, self.mac_address, self.device_type, self.sponsor,
												user_type=self.email_textbox.text())
		else:
			self.registration_thread = RegisterThread(self.username, self.mac_address, self.device_type, self.sponsor,
												user_type=self.user_type)
		self.registration_thread.signals.clear_textboxes_signal.connect(self.clear_textboxes)
		self.registration_thread.signals.disable_widgets_signal.connect(self.disable_widgets)
		self.registration_thread.signals.popup_signal.connect(self.popup_msg)
		self.registration_thread.signals.label_update_signal.connect(self.update_label)
		self.registration_thread.signals.play_splash_signal.connect(self.play_splash)
		self.registration_thread.signals.set_button_clicked_signal.connect(self.set_button_clicked)

		self.thread_pool.start(self.registration_thread)

	# If the user clicks the red button to exit the window
	@Slot()
	def closeEvent(self, event):
		if self.button_clicked:
			while True:
				try:
					self.registration_thread.browser.quit()
					break
				except AttributeError:
					pass

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
