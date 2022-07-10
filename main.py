import os, re, datetime, base64
import wget, requests
import psycopg2
import convertapi
from time import sleep
from random import choice
from math import log
import telebot
from telebot import types
from bs4 import BeautifulSoup

# Telegram group id for logging events
# Bot should be admin of the group for this to work
group_id = os.environ.get("GROUP_ID")
# Heroku postgres databse url
database_url = os.environ.get("DATABASE_URL")
# Convertapi secret token
convertapi_secret = os.environ.get("CONVERTAPI_SECRET")
# Webshare rotating username-rotate:password
webshare_user = os.environ.get("WEBSHARE_USER")
# Webshare api secret token
# This is required to get a static ip address
webshare_token = os.environ.get("WEBSHARE_TOKEN")
# Telegram bot token
bot_token = os.environ.get("TELEGRAM_API")

bot = telebot.TeleBot(bot_token, parse_mode="HTML")

header = {
	'Connection': 'keep-alive',
	'Upgrade-Insecure-Requests': '1',
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Safari/537.36',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
	'Accept-Language': 'en-IN,en;q=0.9',
	'Accept-Encoding': 'gzip, deflate'
}

# Returns user's full name and username
def get_username(message_object):
	name = str(message_object.from_user.first_name)

	last_name = message_object.from_user.last_name

	if last_name:
		name += f" {str(last_name)}"
	
	if "<" in name:
		name = name.replace("<","&lt;")
	
	username = message_object.from_user.username

	if username:
		username = "@" + str(username)
	else:
		username = "None"

	return name, username

# Add a user to database
def add(user_id, num_searches, last_message, user_sites, page_num, member_type, date, info):

	connection = psycopg2.connect(database_url)

	cur = connection.cursor()

	cur.execute('''INSERT INTO users (user_id, num_searches, last_message, user_sites, page_num, member_type, date, info) VALUES (%s,%s,%s,%s,%s,%s,%s,%s);''', (user_id, num_searches, last_message, user_sites, page_num, member_type, date, info))

	connection.commit()

	connection.close()


# Search user data by telegram user_id
def search(user_id):
	connection = psycopg2.connect(database_url)

	cur = connection.cursor()

	cur.execute("SELECT * FROM users WHERE user_id = %s;", (user_id,))

	data = cur.fetchall()

	connection.close()

	num_searches = last_message = user_sites = page_num = member_type = date = info = None

	for row in data:
		(
			num_searches,
			last_message,
			user_sites,
			page_num,
			member_type,
			date,
			info
		) = (row[1], row[2], row[3], row[4], row[5], row[6], row[7])

	return num_searches, last_message, user_sites, page_num, member_type, date, info


# Update database
def update(user_id, num_searches, last_message, user_sites, page_num, member_type, date, info):
	connection = psycopg2.connect(database_url)

	cur = connection.cursor()

	cur.execute('''UPDATE users SET num_searches = %s, last_message = %s, user_sites = %s, page_num = %s, member_type = %s, date = %s, info = %s WHERE user_id = %s;''', (num_searches, last_message, user_sites, page_num, member_type, date, info, user_id))

	connection.commit()

	connection.close()


# Returns a list of available books, containing book's
# details as dictionary
def bcc_search(search_query):
	# Important
	# Host this script on eu-server, else b-ok.global won't work
	response = requests.get(
		f"https://b-ok.global/s/{search_query}",
		headers=header
	)

	soup = BeautifulSoup(response.content, 'html.parser')

	books = soup.find_all('table', class_='resItemTable')

	book_data = []

	for book in books:
		name_header = book.select("h3[itemprop='name']")

		link = name_header[0].find('a')

		book_name = link.text

		book_link = link['href']

		prop_year = book.find('div', class_='property_year')

		if prop_year:
			book_year = prop_year.find('div', class_='property_value').text
		
		else:
			book_year = ''
		
		prop_file = book.find('div', class_='property__file')

		metadata = prop_file.find('div', class_='property_value')

		file_type, file_size = metadata.text.split(',')

		file_size = file_size.strip()

		author_div = book.find('div', class_='authors')

		author_list = author_div.select("a[itemprop='author']")

		authors = []

		for author in author_list:
			authors.append(author.text)
		
		book_data.append({
			"book_name": book_name,
			"link": book_link,
			"authors": authors,
			"upload_year": book_year,
			"file_format": file_type,
			"file_size": file_size
			})
	
	return book_data

# Returns a specific book details
# Book link (e.g. /book/5422789/495673) is required as parameter
def bcc_info(book_link):
	login = f"http://{webshare_user}@p.webshare.io:80"

	webshare = {
		"http": login, "https": login
	}

	# https://3lib.net is global (us, de, spain, brazil) server
	# We can use b-ok.global if script is hosted on eu-servers
	response = requests.get(
		"https://3lib.net" + book_link,
		headers=header,
		proxies=webshare
	)

	soup = BeautifulSoup(response.content, 'html.parser')

	container = soup.find('div', class_='cardBooks')

	title = container.select("h1[itemprop='name']")[0].text.strip()

	cover = container.find('div', class_='z-book-cover')

	if cover:
		cover_img = cover.img['src']
	else:
		cover_img = ""

	author_data = container.select("a[itemprop='author']")

	author_list = [link.text for link in author_data]

	authors = " • ".join(author_list)

	prop_file = container.find('div', class_='property__file')

	metadata = prop_file.find('div', class_='property_value')

	file_type, file_size = metadata.text.split(',')

	file_size = file_size.strip()

	prop_year = container.select("div.property_year > div.property_value")

	if prop_year:
		year = prop_year[0].text
	else:
		year = ""

	prop_publisher = container.select("div.property_publisher > div.property_value")

	if prop_publisher:
		publisher = prop_publisher[0].text
	else:
		publisher = ""

	prop_pages = container.select("div.property_pages > div.property_value")

	if prop_pages:
		pages = prop_pages[0].span.text
	else:
		pages = ""

	prop_isbn = container.find('div', class_='bookProperty property_isbn 13')

	if prop_isbn:
		isbn = prop_isbn.find('div', class_='property_value').text
	else:
		isbn = ""

	return {
		'title': title,
		'authors': authors,
		'cover_img': cover_img,
		'year': year,
		'publisher': publisher,
		'pages': pages,
		'isbn': isbn,
		'file_type': file_type,
		'size': file_size
	}


# Downloads the book from global (https://3lib.net) server
# Fixed ip is required for each request
def bcc_download(user_id, book_link, extention):
	# Get list of fresh webshare ips
	response = requests.get(
		"https://proxy.webshare.io/api/proxy/list",
		headers={
			"Authorization": "Token " + webshare_token
		})

	data = response.json()

	# Pick a random ip
	# This ip will be used for subsequent requests
	picker = choice(data['results'])

	login = f"http://{picker['username']}:{picker['password']}@{picker['proxy_address']}:{str(picker['ports']['http'])}"

	webshare = {
		"http": login, "https": login
	}

	try:
		response = requests.get(
			"https://3lib.net" + book_link,
			proxies=webshare,
			allow_redirects=False
		)

	except:
		bot.send_message(user_id, '⚠️ Something went wrong')

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>⚠️ Event: </b>Dead proxy ~ 210078\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Proxy: </b>{login}")

		return
	
	soup = BeautifulSoup(response.content, 'html.parser')

	link = soup.find('a', class_='btn btn-primary dlButton addDownloadedBook')

	if link:
		download_link = link['href']
	
	# Download link not found
	# Check if file was deleted due to dmca
	else:
		deleted = soup.find('a', class_='btn btn-primary dlButton disabled')

		if deleted:
			bot.send_message(user_id, '⚠️ Link deleted by legal owner')
			
		else:
			bot.send_message(user_id, '⚠️ Something went wrong')
			
			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>⚠️ Event: </b>Download link not fount for book ~ code: 325247\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Proxy: </b>{login}")

		return

	book_name = soup.select("h1[itemprop='name']")[0].text.strip()

	book_name_full = book_name

	# This is name for saving the downloaded e-book
	# Remove invalid characters and add file extention to name
	book_name = book_name[:32]

	invalid_chars = ['!', '@', '#', '$', '%', '^', '&', '*', '+', '\'', '"', '\\', '/', ',', '~', '|', '`', '<', '>', ';', ':', '?']

	book_name = book_name.translate({ ord(char) : ' ' for char in invalid_chars })

	book_name = book_name.strip() + "." + extention.lower()

	book_name = book_name.replace("  ", " - ")

	# Response containes download link in header
	try:
		book_data = requests.get(
			f"https://3lib.net{download_link}",
			proxies=webshare,
			allow_redirects=False
		).headers

	except:
		bot.send_message(user_id, '⚠️ Something went wrong')

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>⚠️ Event: </b>Download failed ~ 217014\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Proxy: </b>{login}")

		return

	# Download link
	redirect = book_data.get('Location')

	if redirect:
		# Error due to ip mismatch
		if 'wrongHash' in redirect:
			bot.send_message(user_id, '📤 Something went wrong')

			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Bot Reply: </b>IP mismatch: wrong hash\n\n<b>Proxy: </b>{login}")

		# Download book and send it to user
		else:
			try:
				filename = wget.download(redirect, 'Downloads/' + book_name)
			
			# Download failed due to network error or dead link
			except:
				bot.send_message(user_id, "📤 Couldn't download book")

				return

			book = open(os.path.join(os.getcwd(), filename), 'rb')

			caption = "📖 <b>" + book_name_full + "</b>"

			bot.send_document(user_id, book, caption=caption)

			book.close()

			os.unlink(os.path.join(os.getcwd(), filename))

			bot.send_message(group_id, f"<b>User ID:</b> hidden\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Event: </b>Book download success\n\n<b>Proxy: </b>{login}")

	# Download link not found
	else:
		bot.send_message(user_id, '📤 Something went wrong')

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>https://3lib.net{book_link}\n\n<b>Event: </b> No redirect location\n\n<b>Proxy: </b>{login}")

# Downloads the book from libgen server
# Download using cloudflare (fast) link if cloudflare param is true
# If convert is true, e-book is converted to pdf after download
def libgen_download(user_id, link, extention, cloudflare=None, book_size=1, convert=False):
	login = f"http://{webshare_user}@p.webshare.io:80"

	webshare = {
		"http": login, "https": login
	}
	try:
		response = requests.get(
			f"http://library.lol/main/{link}",
			headers=header,
			proxies=webshare
		)
	except:
		bot.send_message(user_id, "⚠️ Something went wrong")

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>http://library.lol/main/{link}\n\n<b>Event: </b>⚠️ Couldn't connect to library.lol (315529)")

		return

	soup = BeautifulSoup(response.content, 'html.parser')

	book_name = soup.find('h1').text

	download_div = soup.find(id='download')

	# Libgen direct download link
	download_link = download_div.find('h2').a['href']

	# Cloudflare download link
	fast_download = download_div.ul.li.a['href']

	# Use full name for caption
	caption = "📖 <b>" + book_name + "</b>"
	
	book_name = book_name[:32]

	invalid_chars = ['!', '@', '#', '$', '%', '^', '&', '*', '+', '\'', '"', '\\', '/', ',', '~', '|', '`', '<', '>', ';', ':', '?']

	book_name = book_name.translate({ ord(char) : ' ' for char in invalid_chars })

	extention = extention.lower()

	book_name = book_name.strip() + "." + extention

	book_name = book_name.replace("  ", " - ")

	# Use fast server if cloudflare param is true
	if cloudflare:
		download_link = fast_download

	# Download book and convert to pdf
	if convert:
		convertapi.api_secret = convertapi_secret
		
		try:
			result = convertapi.convert('pdf',{
				'File': download_link
				}, from_format = extention, timeout=300)
		
		except convertapi.exceptions.ApiError as e:
			if 'Parameter validation error' in e.message:
				bot.send_message(user_id, f"⚠️ Cannot convert .{extention} files")
			
			elif 'Invalid user credentials' in e.message:
				bot.send_message(user_id, "⚠️ Conversion feature is disabled")

				bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>⚠️ Conversion failed (315149)\n\n<b>Reason: </b>Invalid convert-api credentials")
			
			else:
				bot.send_message(user_id, "⚠️ Something went wrong")

				bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>⚠️ Conversion failed (315167)")

			return

		location = result.file.save('Converted/' + os.path.splitext(book_name)[0]+'.pdf')

		book = open(location, 'rb')

		bot.send_document(user_id, book, caption=caption + "\n\nConverted to pdf by —(@Bookemybot)")

		book.close()

		os.unlink(location)

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>Converted .{extention} to .pdf\n\nCredits <b>({result.conversion_cost})</b>")
	
	else:
		# Book size is within download limit
		# Files greater than 250 MB can't be uploaded to file.io
		if book_size < 250:
			try:
				filename = wget.download(download_link, 'Downloads/' + book_name)

			# Download failed due to network error or dead link
			except:
				bot.send_message(user_id, "📤 Couldn't download book")

				return
			
			book = open(os.path.join(os.getcwd(), filename), 'rb')

			# Books less than 50 MB can be directly sent over telegram
			if book_size < 50:
				if extention == 'pdf':
					bot.send_document(user_id, book, caption=caption)

				# Book is not .pdf format
				# Send markup, ask if user wants to convert to pdf
				else:
					markup = types.InlineKeyboardMarkup()

					foodie = choice(['🍿','🍟','🍧','🍷','🍜','🍕','🍝','🍨'])

					convert_btn = types.InlineKeyboardButton(foodie + " Convert to pdf (free)", callback_data="convert~" + link + "~" + extention + "~" + str(book_size))

					markup.row(convert_btn)

					bot.send_document(user_id, book, caption=caption, reply_markup=markup)

			# Book size between 50 and 250 MB
			# Upload book to file.io cloud and send download link
			else:
				try:
					upload = requests.post(
						'https://file.io',
						files = { "file": book }
					).json()
				except:
					bot.send_message(user_id, "⚠️ Something went wrong")

					bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>Upload to file.io failed.\n\<b>Error code: </b>617293")

					# Book upload failed
					# Close and delete the downloaded e-book
					book.close()

					os.unlink(os.path.join(os.getcwd(), filename))
					
					return

				# File upload success
				# Send the download link received from file.io
				if upload['success']:
					bot.send_message(user_id, upload['link'])
				
				else:
					bot.send_message(user_id, "⚠️ Something went wrong")

					bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>Upload to file.io failed.\n\<b>Error code: </b>617112")

			book.close()

			os.unlink(os.path.join(os.getcwd(), filename))

		else:
			bot.send_message(user_id, "⚠️ Unsupported file size")
		
		bot.send_message(group_id, f"<b>User ID:</b> hidden\n\n<b>Book Link: </b>{download_link}\n\n<b>Event: </b>Book download success")


# Search libgen for e-books
# Returns a list of available books, containing book's
# details as dictionary
def libgen_search(search_query, link=None, filter_with=None, file_type=None):
	login = f"http://{webshare_user}@p.webshare.io:80"

	webshare = {
		"http": login, "https": login
	}

	# Libgen default search
	# It will search in book title and author
	url = f"https://libgen.is/search.php?req={search_query}&open=0&res=25&view=detailed&phrase=1&column=def"

	# Filter search using isbn
	if filter_with == 'isbn':
		if file_type.lower() == 'pdf':
			url = f"https://libgen.is/search.php?req={search_query}&open=0&res=25&view=detailed&phrase=1&column=identifier&sort=extension&sortmode=DESC"
		
		else:
			url = f"https://libgen.is/search.php?req={search_query}&open=0&res=25&view=detailed&phrase=1&column=identifier"

	response = requests.get(
		url,
		headers=header,
		proxies=webshare
	)

	soup = BeautifulSoup(response.content, 'html.parser')

	# Brown line above each book's row
	target = soup.find_all('tr', {'height': '2', 'valign': 'top'})

	book_data = []

	for book in target:
		# Siblings of book contain book's information
		data = book.find_next_siblings()

		part = data[0]

		book_cover = part.a.img['src']
		book_name = part.b.text

		# This is hash of book
		# Slicing removes everything except hash
		book_link = part.a['href'][10:]

		author_data = data[1]

		a = author_data.find_all('a')

		author_list = map(lambda author: author.text, a)

		authors = " • ".join(author_list) 

		publisher = data[3].find('td', text='Publisher:').find_next_sibling().text

		year = data[4].find('td', text='Year:').find_next_sibling().text

		pages = data[5].find('td', text='Pages:').find_next_sibling().text

		size = data[8].find('td', text='Size:').find_next_sibling().text

		# Remove the size in bytes
		size = size.split('(')[0].strip()

		extension = data[8].find('td', text='Extension:').find_next_sibling().text

		extension = extension.upper()

		# User picked a particular book
		# Return that book's details
		if link:
			if book_link == link:
				return {
					'title': book_name,
					'link': book_link,
					'authors': authors,
					'cover_img': book_cover,
					'year': year,
					'publisher': publisher,
					'pages': pages,
					'file_type': extension,
					'size': size
				}

		# User sent a book name
		# Add every book's data to book-data list
		else:
			book_data.append({
				'title': book_name,
				'link': book_link,
				'authors': authors,
				'cover_img': book_cover,
				'year': year,
				'publisher': publisher,
				'pages': pages,
				'file_type': extension,
				'size': size
			})

			# Fast download
			if file_type:
				if file_type.upper() == extension:
					return (book_link, extension)
		
	return book_data


# Returns a list of all udemy courses
def fetch_courses():
	# Final list containes slugified course names e.g. flask-framework
	courses_list = []

	response = requests.get("https://www.discudemy.com/all", headers=header)

	soup = BeautifulSoup(response.content, 'html.parser')

	courses = soup.find_all('a', class_='card-header')

	# New courses
	for course in courses:
		# Removes 'https://www.discudemy.com/category/' from links
		link = re.match('https://www.discudemy.com(/.+)?/(.+)', course['href'])
		courses_list.append(link.group(2))

	popular = soup.find_all('div', class_='five wide column')

	# Popular courses
	for div in popular:
		links = div.find_all('a')

		for link in links:
			# Remove 'http://www.discudemy.com/' from link
			course = link['href'][25:]

			if course not in courses_list:
				courses_list.append(course)

	return courses_list

# Returns actual course name
# Parameter c-name is slugified course name
def course_name(c_name):
	formatted = "⌘  " + " ".join(map(lambda word: word.capitalize(), c_name.split('-')))
		
	# Prevents accidently removing last "-" from real url
	if c_name.endswith("-"):
		formatted = formatted.strip() + "-"

	return formatted

# Converts course name to slug
# Fetches the course coupon and returns udemy link
def get_coupon(user_choice):
	# Slicing removes ⌘ 
	course_meta = user_choice[3:].replace(" ", "-")

	response = requests.get("http://www.discudemy.com/go/" + course_meta, headers=header)

	soup = BeautifulSoup(response.content, 'html.parser')

	coupon_link = soup.find(id="couponLink")

	return coupon_link['href']


# Adds a list of courses as buttons
# Button-text is list of all courses or searched e-books
# Current-page can be "b-ok", "archive" or "libgen"
def add_buttons(button_text, is_udemy=False, current_page=False):
	markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)

	if current_page:
		pages = {
			'b-ok': ['①', '➋', '➌'],
			'archive': ['➊', '②', '➌'],
			'libgen': ['➊', '➋', '③']
		}
		
		nav = pages[current_page]
		
		markup.add(
			types.KeyboardButton('🔙'),
			types.KeyboardButton(nav[0]),
			types.KeyboardButton(nav[1]),
			types.KeyboardButton(nav[2])
		)

	else:
		markup.add('🔙')

	# Add all courses to buttons
	# Button-text is list of udemy courses
	if is_udemy:
		for text in button_text:
			markup.add(types.KeyboardButton(course_name(text)))
	
	# Button-text is list of all e-books
	else:
		for text in button_text:
			markup.add(types.KeyboardButton(text))

	return markup


def keyboard(one, two, three):
	markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

	markup.add(
		types.KeyboardButton(one),
		types.KeyboardButton(two),
		types.KeyboardButton(three)
	)
	markup.add('🔙')

	return markup

# Function runs on callback from inline buttons
@bot.callback_query_handler(func=lambda call: True)
def downloader(call):
	cid = call.message.chat.id
	uid = call.from_user.id
	mid = call.message.message_id

	# Callback is from admin group (reply to user's feedback button)
	# Send a force-reply with user and message id
	if str(cid) == group_id:
		user_id, message_id = call.data.split("~")

		markup = types.ForceReply()

		bot.send_message(group_id, user_id + " • " + message_id, reply_markup=markup)

		return

	metadata = call.data

	site_id, book_link, extention, size = metadata.split('~')

	if 'mb' in size:
		size_mb = round(float(size.split('mb')[0].strip()))

	elif 'kb' in size:
		size_mb = 1

	# Download link of b-ok
	if site_id == "3247":
		wait = round(log(size_mb) * 10) + size_mb + 5

		if wait > 60:
			minute, sec = divmod(wait, 60)

			bot.answer_callback_query(call.id, text="Downloading (please wait) ...			" + str(minute) + " minute " + str(sec) +" seconds")

		else:
			bot.answer_callback_query(call.id, text="Downloading (please wait) ...			" + str(wait) + " seconds")

		bcc_download(uid, book_link, extention)
	
	# Download link of libgen
	elif site_id == "5241":
		bot.answer_callback_query(call.id, text="Downloading (please wait) ...			" + str(round(size_mb + choice([4, 5, 6, 7, 8, 9]))) + " seconds")

		libgen_download(uid, book_link, extention, book_size=size_mb)

	# Download link of libgen (cloudflare) and convert
	elif site_id == "convert":
		size = round(float(size))

		# Convert files less than 10 MB
		if size < 11:
			if size < 5:
				wait = 48 + size
				
				bot.answer_callback_query(call.id, text=f"Converting (please wait) ...			{wait} seconds")
			
			else:
				wait = 13 + size

				bot.answer_callback_query(call.id, text=f"Converting (please wait) ...			1 minute {wait} seconds")
			
			libgen_download(uid, book_link, extention, cloudflare=True, book_size=size, convert=True)
		
		else:
			bot.send_message(user_id, "⚠️ File size too big")

	# Fast download
	# Search isbn in libgen and download using cloudflare
	else:
		if size_mb < 100:
			wait = round(log(size_mb) * 8) + size_mb + 4

		else:
			wait = '∞'

		bot.answer_callback_query(call.id, text=f"Downloading (please wait) ...			{wait} seconds")

		try:
			book_link, extention = libgen_search(book_link, filter_with='isbn', file_type=extention)

		except ValueError:
			bot.send_message(uid, "⚠️ Book not on fast server")
			
			bot.send_message(group_id, f"<b>User ID:</b> hidden\n\n<b>Event: </b>⚠️ Book not on fast server\n\n<b>ISBN: </b>{book_link}")

			book_link = None

		if book_link:
			libgen_download(uid, book_link, extention, cloudflare=True, book_size=size_mb)


# User started the bot
# Sending a command /start to bot runs this function
@bot.message_handler(commands=['start'])
def send_welcome(message):
	user_id = str(message.chat.id)

	if user_id == group_id:
		return
	
	name = get_username(message)[0]
	username = get_username(message)[1]

	markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

	book_icon = choice(['📘', '📙', '📗', '📒', '📕', '📔', '📓'])

	video_icon = choice(['📀', '💿'])

	itembtn1 = types.KeyboardButton(video_icon + ' Courses')
	itembtn2 = types.KeyboardButton(book_icon + ' E-books')
	itembtn3 = types.KeyboardButton('Settings')

	markup.add(itembtn1, itembtn2, itembtn3)

	if str(message.text) == "/start":
		bot.send_message(
			user_id,
			f"Hello <b>{name}</b>👤\n\nWelcome to <b>Bookemy</b> 🌼\n\n<b>Bookemy</b> 🌼 makes downloading e-books fast and fun. Just send name of the book to download e.g. <b>Atomic Habits</b> and see the magic",
			reply_markup=markup
		)

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>☘️ Started bot")


# Function executes when user sends a message to bot
@bot.message_handler(func=lambda message: True)
def echo_all(message):
	user_id, usr_message = str(message.chat.id), str(message.text)

	# Message sent in group (admin)
	if user_id == group_id:
		grp_replied = message.reply_to_message.json['from']['username']

		# Check if we are replying to bot
		# Multiple admins can reply to each other without bot's interference
		if grp_replied == 'Bookemybot':
			replied_to = message.reply_to_message.text

			usr_id, msg_id = replied_to.split(' • ')

			try:
				bot.send_message(usr_id, usr_message + "\n\n—(@Bookemybot)", reply_to_message_id=msg_id)

			except Exception as e:
				if 'bot was blocked by the user' in e:
					bot.send_message(group_id, "Error: blocked by user")
				
				else:
					bot.send_message(group_id, '⚠️ Something went wrong')
					print(e)

		return

	message_id = str(message.message_id)

	name = get_username(message)[0]
	username = get_username(message)[1]

	num_searches, last_message, user_sites, page_num, member_type, date, info = search(user_id)

	today = str(datetime.date.today())
	
	button_list = ['Settings', 'Friends', 'Websites', 'Feedback', '▪️Feedback', '🔙']

	# User doesn't exist in database, set defaults
	if not member_type:
		num_searches = f'0--{today}'
		user_sites = '1-1-0'
		page_num = '0'

	if usr_message in button_list:
		usr_message = usr_message.strip('▪️')

		# User doesn't exist in db
		if not member_type:
			add(user_id, num_searches, usr_message, user_sites, page_num, "free", today, info)

		else:
			# Update the last message
			update(user_id, num_searches, usr_message, user_sites, page_num, member_type, date, info)

		if usr_message == "Settings":
			markup = keyboard('Friends', 'Websites', 'Feedback')

			bot.send_message(user_id, "Select an option:", reply_markup=markup)

		elif usr_message == "Feedback":
			# User cancelled feedback
			if last_message == 'Feedback':
				# Update the last message to settings-page
				update(user_id, num_searches, 'Settings', user_sites, page_num, member_type, date, info)

				markup = keyboard('Friends', 'Websites', 'Feedback')

				bot.send_message(user_id, "Feedback cancelled", reply_markup=markup)
			
			else:
				markup = keyboard('Friends', 'Websites', '▪️Feedback')

				bot.send_message(user_id, "Send me your message ~", reply_markup=markup)


		# Option to add friends & share e-books
		elif usr_message == "Friends":
			markup = keyboard('New friend', 'Remove a friend', 'Help')

			bot.send_message(user_id, "You are friends with 👤 <b>None</b>", reply_markup=markup)

		# Back button
		else:
			# Cancel feedback
			# Update last message to settings
			if last_message == 'Feedback':
				update(user_id, num_searches, 'Settings', user_sites, page_num, member_type, date, info)

				markup = keyboard('Friends', 'Websites', 'Feedback')

				bot.send_message(user_id, "Feedback cancelled", reply_markup=markup)
			
			# Home
			else:
				eatmoji = ['🍏','🍎','🍊','🍋','🍌','🍉','🍓','🍇','🍒','🍅','🥑','🥬','🥒','🍞','🌭','🍔','🍟','🍕','🥪','🌮','🍜','🍣','🍧','🍿','🍷']

				markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

				book_icon = choice(['📘', '📙', '📗', '📒', '📕', '📔', '📓'])

				video_icon = choice(['📀', '💿'])

				itembtn1 = types.KeyboardButton(video_icon + ' Courses')
				itembtn2 = types.KeyboardButton(book_icon + ' E-books')
				itembtn3 = types.KeyboardButton('Settings')

				markup.add(itembtn1, itembtn2, itembtn3)

				bot.send_message(user_id, "We're back home " + choice(eatmoji), reply_markup=markup)

	# User sent a feedback
	elif last_message == "Feedback":
		# Update the last message to settings
		update(user_id, num_searches, 'Settings', user_sites, page_num, member_type, date, info)

		markup = keyboard('Friends', 'Websites', 'Feedback')

		bot.send_message(
			user_id,
			"Thank you for feedback💚",
			reply_markup=markup
		)

		markup = types.InlineKeyboardMarkup()

		button = types.InlineKeyboardButton("Reply to user", callback_data=user_id + "~" + message_id)

		markup.row(button)

		bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Message ID: </b>{message_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b>{usr_message}\n\n<b>Bot Reply:</b> Thank you for feedback💚", reply_markup=markup)

	# User message not in button list
	else:
		# Fetch all udemy courses
		if usr_message.startswith(('📀', '💿')):
			markup = add_buttons(fetch_courses(), is_udemy=True)

			bot.send_message(user_id, "Choose required course:", reply_markup=markup)

			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>User clicked courses-btn")

		# Ask user to send name of book
		elif usr_message.startswith(('📘', '📙', '📗', '📒', '📕', '📔', '📓')):
			# Logger
			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>User clicked ebooks-btn")

			text = bot.send_message(user_id, "∙∙∙  Send me a book name ~")

			# No. of times animation should repeat
			for counter in range(int(5)):
				for icon in ["●∙∙", "∙●∙", "∙∙●", "∙∙∙ "]:

					sleep(0.5)
				
					bot.edit_message_text(
						f"{icon} Send me a book name ~",
						user_id,
						text.message_id
					)

		# User sent a udemy course, reply with coupon
		elif usr_message.startswith("⌘"):
			udemy_link = get_coupon(usr_message.lower())

			if udemy_link == "error: invalid link":
				bot.send_message(user_id, '⚠️ Something went wrong')

				# Logger
				bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b> {usr_message}\n\n<b>Bot Reply: </b>⚠️ Something went wrong")

			else:
				bot.send_message(user_id, udemy_link)

				# Logger
				bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b>⌘ Udemy Course ~ hidden\n\n<b>Bot Reply: </b>Link ~ hidden")

		# Send books from archive
		elif usr_message == "➋" or usr_message == "②":
			book_searched = last_message.strip("✢ ")

			book_details = []

			markup = add_buttons(book_details, current_page='archive')

			bot.send_message(user_id, "⚠️ Currently unavailable", reply_markup=markup)

			# markup = add_buttons(book_details, current_page='archive')
			# bot.send_message(user_id, "✤ Results from <b>archive (fast)</b>", reply_markup=markup)

		# Send books from libgen
		elif usr_message == "➌" or usr_message == "③":
			book_searched = last_message.strip("✢ ")

			book_details = []

			all_books = libgen_search(book_searched)

			for book in all_books:
				metadata = "5241~" + book['link']

				enc_byte = metadata.encode('ascii')
				encoded_meta = base64.b64encode(enc_byte).decode('ascii')
			
				book_details.append(book['title'][:32] + " (" + book['year'] + ")\n" + book['authors'].split(" • ")[0][:25] + " • " + book['file_type'] + "\n" + encoded_meta)

			try:
				first_book = book_details[0]

			except IndexError:
				first_book = 'None'

			markup = add_buttons(book_details, current_page='libgen')

			bot.send_message(user_id, "✤ Results from <b>libgen (fast)</b>", reply_markup=markup)

			# Logger
			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b>{usr_message}\n\n<b>First Result: </b>{first_book}")

	
		elif usr_message == "➊" or usr_message == "①":
			book_searched = last_message.strip("✢ ")

			book_details = []

			all_books = bcc_search(last_message)

			for book in all_books:
				metadata = "3247~" + book['link']

				enc_byte = metadata.encode('ascii')
				encoded_meta = base64.b64encode(enc_byte).decode('ascii')
			
				book_details.append(book['book_name'][:32] + " (" + book['upload_year'] + ")\n" + book['authors'][0][:25] + " • " + book['file_format'] + "\n" + encoded_meta)
				
			try:
				first_book = book_details[0]

			except IndexError:
				first_book = 'None'

			markup = add_buttons(book_details, current_page='b-ok')

			bot.send_message(user_id, "✤ Results from <b>b-ok (slow)</b>", reply_markup=markup)

			# Logger
			bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b>{usr_message}\n\n<b>First Result: </b>{first_book}")

		# User picked a book from list
		else:
			# Send book details
			if "\n" in usr_message:
				metadata = usr_message.split("\n")

				enc_byte = metadata[-1].encode('ascii')
				decoded_meta = base64.b64decode(enc_byte).decode('ascii')

				site_id, link = decoded_meta.split('~')

				extention = metadata[-2].split('•')[-1].strip()

				# Site id for b-ok
				if site_id == '3247':
					book_info = bcc_info(link)

					if book_info['title'] == 'error':
						bot.send_message(user_id, "⚠️ Something went wrong")

						bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>User sent e-book name (from list)\n\n<b>Link: </b>https://b-ok.cc{link}\n\n<b>Bot Reply: </b> ⚠️ Something went wrong")

					else:
						size = book_info['size'].lower()

						markup = types.InlineKeyboardMarkup()

						download_btn = types.InlineKeyboardButton("⏳ Download", callback_data=site_id + '~' + link + '~' + extention + '~' + str(size))

						if book_info['isbn']:
							smart_download = types.InlineKeyboardButton("⚡️ Download", callback_data="isbn~" + book_info['isbn'] + "~" + extention + '~' + str(size))

							markup.row(download_btn, smart_download)
						
						# Book doesn't have isbn
						# Search by title & append book link
						else:
							title = ""

							words = book_info['title'].split(" ")

							for word in words:
								if len(title) <= 77:
									title += word + " "

							book_matched = libgen_search(title.strip(), file_type=extention)

							# No book matched with extention specified --> list
							# Book matched --> tuple
							if isinstance(book_matched, tuple):
								link, extention = book_matched

								smart_download = types.InlineKeyboardButton("🌩 Download", callback_data='5241~' + link + '~' + extention + '~' + str(size))

								markup.row(download_btn, smart_download)

							else:
								markup.row(download_btn)

						caption = "<b>" + book_info['title'] + "</b>\n\n<b>Author(s): </b>" + book_info['authors'] + "\n\n<b>" + extention + " (" + str(book_info['pages']) + " pages) • " + book_info['size'] + "</b>\n\n<b>Publisher: </b>" + str(book_info['publisher'])

						try:
							bot.send_photo(user_id, book_info['cover_img'], caption, reply_markup=markup)

						except:
							bot.send_message(user_id, caption, reply_markup=markup)

						bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>User sent e-book name (from list) ~ hidden\n\n<b>Bot Reply: </b>site-id: {site_id} ~ hidden")

				elif site_id == "5241":
					book_searched = last_message.strip("✢ ")

					book_info = libgen_search(book_searched, link)

					size = book_info['size'].lower()
					
					markup = types.InlineKeyboardMarkup()

					button = types.InlineKeyboardButton("Download", callback_data=site_id + '~' + link + '~' + extention + '~' + str(size))

					markup.row(button)

					caption = "<b>" + book_info['title'] + "</b>\n\n<b>Author(s): </b>" + book_info['authors'] + "\n\n<b>" + extention + " (" + str(book_info['pages']) + " pages) • " + book_info['size'] + "</b>\n\n<b>Publisher: </b>" + str(book_info['publisher'])

					try:
						bot.send_photo(user_id, 'http://libgen.is' + book_info['cover_img'], caption, reply_markup=markup)

					except:
						bot.send_message(user_id, caption, reply_markup=markup)

					# Logger
					bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>Event: </b>User sent e-book name (from list) ~ hidden\n\n<b>Bot Reply: </b>site-id: {site_id} ~ hidden")

				else:
					print(f"No match for site id {site_id}")
			
			# Search e-books
			else:
				# Can't store greater than 32-chars in db
				# ✢ can be later used to check if last-message was a book search
				book_searched = '✢ ' + usr_message[:28]

				all_books = bcc_search(usr_message)

				# User doesn't exist in db
				# Add book-searched as last-message
				if not member_type:
					add(user_id, num_searches, book_searched, user_sites, '0', 'free', today, info)

				else:
					update(user_id, num_searches, book_searched, user_sites, '0', member_type, date, info)

				book_details = []

				for book in all_books:
					metadata = "3247~" + book['link']

					enc_byte = metadata.encode('ascii')
					encoded_meta = base64.b64encode(enc_byte).decode('ascii')
				
					book_details.append(book['book_name'][:32] + " (" + book['upload_year'] + ")\n" + book['authors'][0][:25] + " • " + book['file_format'] + "\n" + encoded_meta)
					
				try:
					first_book = book_details[0]

				except IndexError:
					first_book = 'None'

				markup = add_buttons(book_details, current_page='b-ok')

				bot.send_message(user_id, "✤ Results from <b>b-ok (slow)</b>", reply_markup=markup)

				# Logger
				bot.send_message(group_id, f"<b>User ID:</b> {user_id}\n<b>Name: </b>{name}\n<b>Username: </b>{username}\n<b>Permanent link: </b><a href=\"tg://user?id={user_id}\">User</a>\n\n<b>User Message: </b>{usr_message}\n\n<b>First Result: </b>{first_book}")


bot.polling()

	