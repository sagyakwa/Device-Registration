import sys
from os.path import join, dirname, abspath

from qtpy import uic
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication, QMainWindow, QMessageBox
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import ElementNotVisibleException, StaleElementReferenceException, WebDriverException, \
	NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime

import yaml
import qtmodern.styles
import qtmodern.windows
import re
import datetime
import webbrowser
import selenium

_UI = join(dirname(abspath(__file__)), 'mainwindow.ui')


class MainWindow(QMainWindow):
	from PyQt5 import QtGui

	def __init__(self):
		QMainWindow.__init__(self)
		self.ui = uic.loadUi(_UI, self)

		# make browser headless
		options = Options()
		options.headless = False  # Change to True to make headless

		self.browser = webdriver.Chrome(options=options)
		credential_location = join(dirname(abspath(__file__)), 'credentials')
		credentials = yaml.load(open(credential_location))
		self.login_username = credentials['credentials']['username']
		self.login_password = credentials['credentials']['password']
		self.username = None
		self.mac_address = None
		self.device_type = None
		self.sponsor = None

	def play_gif(self):
		gif_path = join(dirname(abspath(__file__)), 'batman.gif')
		global loading_gif
		loading_gif = self.QtGui.QMovie(gif_path)

		self.ui.label_7.setMovie(loading_gif)
		self.ui.label_7.setScaledContents(True)
		loading_gif.start()

	# Function to display an error if we get one
	def error_msg(self, error_string):
		QMessageBox.about(self, 'Errors in your form!', error_string)

	# Check to see if mac address is valid format eg. (00:00:00:00:00:000 or (00-00-00-00-00-00)
	@staticmethod
	def check_mac_address(mac_address):
		return bool(re.match('[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$', mac_address.lower()))

	# Check to see if username is correct format eg. (sagyakwa) or (sagyakwa45)
	@staticmethod
	def check_username(username):
		return bool(re.match(r'[a-zA-Z]{1,}', username.lower()) or (
				re.match(r'[a-zA-Z]{1,}', username.lower()) and username.endswith(re.match(r'[0-9]{1,}'))))

	@staticmethod
	def check_your_name(your_name):
		return bool(re.match(r'[a-zA-Z]{1,}(.*[\s]?)', your_name.lower()))

	# Visit website and log in
	def visit_site(self):
		# Define credentials
		global username, mac_address, device_type, your_name
		# Get the texts entered in the textbox
		self.username = str(self.ui.lineEdit.text())
		self.mac_address = str(self.ui.lineEdit_2.text())
		self.device_type = str(self.ui.lineEdit_3.text())
		self.sponsor = str(self.ui.lineEdit_4.text())

		# Make dictionary to check whether format of text boxes are correct
		global everything
		everything = {
			'right_address': bool(self.check_mac_address(self.mac_address)),
			'right_username': bool(self.check_username(self.username)),
			'right_name': bool(self.check_your_name(self.sponsor))
		}

		# Check to see that there is some text in the Text boxes and it is correctly formatted
		if all(everything.values()):
			# Play the gif
			self.play_gif()
			print('Everything checks out')
			# go to the homepage
			self.browser.get('http://fsunac-1.framingham.edu/administration')
			# Check to see if on school Wifi
			try:
				self.browser.find_element_by_xpath("//*[contains(text(), 'ERR_NAME_NOT_RESOLVED')]")
				self.browser.find_element_by_xpath("//*[contains(text(), 'ERR_INTERNET_DISCONNECTED')]")
			# Continue if we don't find an error message and are connected to the internet
			except NoSuchElementException:
				# increment progress bar
				self.ui.progressBar.setValue(10)
				self.login()
				self.ui.progressBar.setValue(25)
				if self.find_user():
					self.add_device()
				else:
					self.create_new_user()
			else:
				self.error_msg('Check your internet connect \n and make sure you are connected to FSU\'s network')
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
			self.error_msg(msg)
	# Handle any exception we might've forgotten

	def find_and_send_keys(self, xpath, keys_to_send):
		textbox = WebDriverWait(self.browser, 20).until(
			ec.presence_of_element_located(
				(By.XPATH, xpath))
		)

		# self.browser.execute_script(f'arguments[0].value={keys_to_send}', textbox)
		textbox.send_keys(keys_to_send)
		print("Keys sent!")

	def find_and_click(self, xpath):
		clickable_object = WebDriverWait(self.browser, 20).until(
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

			login_button = WebDriverWait(self.browser, 20).until(
				ec.presence_of_element_located(
					(By.XPATH, login_button_xpath))
			)
			login_button.click()
			print('Login successful!')
			self.browser.refresh()
		except NoSuchElementException:
			print('Something ain\'t right')

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
		registration_start_date = current_date.strftime("%m/%d/%Y")
		registration_end_date = f"{current_date.strftime('%m')}/{current_date.strftime('%d')}/{int(current_date.strftime('%Y')) + 2} "

		add_user_button = '//*[@id="showUsersAdd"]'
		username_textbox = '//*[@id="addEditUserTable"]/tbody/tr[4]/td[2]/input'
		email_textbox = '//*[@id="addEditUserTable"]/tbody/tr[5]/td[2]/input'
		start_time_textbox = '//*[@id="regStartTime"]'
		expires_time_textbox = '//*[@id="regExpirationTime"]'
		sponsor_textbox = '//*[@id="addEditUserTable"]/tbody/tr[9]/td[2]/input'
		user_type_dropdown = '//*[@id="addEditUserTable"]/tbody/tr[10]/td[2]/select'
		submit_button = '//*[@id="addUser"]'

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

	# When the button is clicked
	@Slot()
	def on_pushButton_clicked(self):
		self.visit_site()

	# If the user clicks the red button to exit the window
	@Slot()
	def closeEvent(self, event):
		# noinspection PyCallByClass
		reply = QMessageBox.question(self, 'Leaving so soon?', 'Do you want to exit?\n\n')

		# if they reply yes, exit window
		if reply == QMessageBox.Yes:
			event.accept()
			self.browser.quit()
		# if they reply no, stay where you are
		else:
			event.ignore()


if __name__ == '__main__':
	app = QApplication(sys.argv)

	qtmodern.styles.dark(app)
	mw = qtmodern.windows.ModernWindow(MainWindow())
	mw.show()

	sys.exit(app.exec_())
