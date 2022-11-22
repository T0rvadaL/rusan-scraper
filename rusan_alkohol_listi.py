#https://rusan.fo/
# Volume * %alc(decimal) / prís --> ml_av_alc/1kr.

import re
import requests
from bs4 import BeautifulSoup
from time import sleep
from csv import DictWriter
from operator import itemgetter

base_url = 'https://rusan.fo/'
goto_url = '/ShopCategoryItemPictureList/ALKOHOLFRIVIN/0'
res = requests.get(f'{base_url}{goto_url}')
soup = BeautifulSoup(res.text, 'html.parser')
name_hook = soup.find_all(class_='ItemTable show-on-mobile shop-cat-mobile-title')
beverage_data = soup.find_all(class_='InformationTable')
category = soup.find(class_='Main current').find('a').get_text()
sub_category = soup.find(class_='Sub current').find('a').get_text()
index = 0
page_index = 1
sub_index = 1
main_index = 1

name_list = []
beverage_list = []

case_regex = re.compile(r'\(\d+|\d+\)')

'''
\d{1,}
'''
while True:
	for names in name_hook:
		name = names.find('a').get_text()
		name_list.append(name)

	for beverage in beverage_data:
		innihald_raw = beverage.find_all(class_='InformationRow')[2].find_all('div')[1].get_text()
		innihald_ml = float(innihald_raw[:-15].replace(',','.')) * 1000
		innihald_l = float(innihald_raw[:-15].replace(',','.'))
		styrki_raw = innihald_raw = beverage.find_all(class_='InformationRow')[3].find_all('div')[1].get_text()
		styrki_decimal = float(styrki_raw[:-10].replace(',','.')) / 100
		styrki_prosent = styrki_raw[10:-9].replace(',','.')
		price_raw = beverage.find_all(class_='InformationRow')[-1].find_all('div')[1].get_text()
		price_converted = price_raw[10:-10].replace(',','.')
		try:
			price = float(price_raw[10:-10].replace(',','.'))
		except:
			price = ''
			count = 0
			for p in price_converted:
				if p == '.' and count == 0:
					count += 1
					continue
				price += p
			price = float(price)
		
		alc_kr_raw = innihald_ml * styrki_decimal / price

		# regex_string = case_regex.search(name_list[index])
		regex_string = case_regex.search(name_list[index])
		try:
			quantity = ''
			quantity_filter = regex_string.group()
			for num in quantity_filter:
				if num.isdigit():
					quantity += num
			# print(f'-------------------------- {alc_kr_raw}')
			alc_kr_raw *= int(quantity)
			# print(f'alk/kr ratio er {alc_kr_raw}')
		except:
			None
		# print(alc_kr_raw)
		alc_kr = f'{round(alc_kr_raw, 2)}/kr.'

		beverage_list.append({
				'Bólkur': category,
				'Undir-Bólkur': sub_category,
				'Navn': name_list[index],
				'Innihald': innihald_l,
				'Styrki': styrki_prosent,
				'Prísur': price,
				'Alk/kr': alc_kr
			})
		index += 1
		
	if category == 'Øl':
		try:
			goto_url = soup.find(class_='PagingNumbers').find_all('a')[page_index]['href']
			page_index += 1
		except:
			main_data = soup.find(class_='VerticalMenu').find_all(class_='Main')[main_index].find('a')
			goto_url = main_data['href']
			category = main_data.get_text()
			sub_index = 1
			page_index = 1
			main_index += 1
	elif category == 'Cider':
		try:
			goto_url = soup.find(class_='PagingNumbers').find_all('a')[page_index]['href']
			page_index += 1
		except:
			break
	else:
		try:
			goto_url = soup.find(class_='PagingNumbers').find_all('a')[page_index]['href']
			page_index += 1
		except:
			try:
				link_data = soup.find(class_='SubContainer current Open').find_all(class_='Sub')[sub_index].find('a')
				goto_url = link_data['href']
				sub_category = link_data.get_text()
				sub_index += 1
				page_index = 1
			except:
				main_data = soup.find(class_='VerticalMenu').find_all(class_='Main')[main_index].find('a')
				category = main_data.get_text()
				if category != 'Øl':
					fetch_url = main_data['href']
					res2 = requests.get(f'{base_url}{fetch_url}')
					soup2 = BeautifulSoup(res2.text, 'html.parser')
					goto_url = soup2.find(class_='SubContainer current Open').find('a')['href']
				else:
					goto_url = main_data['href']
				sub_index = 1
				page_index = 1
				main_index += 1

	sleep(1)
	res = requests.get(f'{base_url}{goto_url}')
	soup = BeautifulSoup(res.text, 'html.parser')
	name_hook = soup.find_all(class_='ItemTable show-on-mobile shop-cat-mobile-title')
	beverage_data = soup.find_all(class_='InformationTable')
	category = soup.find(class_='Main current').find('a').get_text()
	try:
		sub_category = soup.find(class_='Sub current').find('a').get_text()
	except:
		sub_category = 'Ongin'
	print(f'Scraping {goto_url}')

beverage_list = sorted(beverage_list, key=itemgetter('Bólkur', 'Undir-Bólkur', 'Alk/kr'))

with open('rusan_alkohol_list.csv', 'w', newline='') as file:
	fieldnames = 'Bólkur', 'Undir-Bólkur', 'Navn', 'Innihald', 'Styrki', 'Prísur', 'Alk/kr'
	csv_writer = DictWriter(file, fieldnames = fieldnames)
	csv_writer.writeheader()
	for bev in beverage_list:
		csv_writer.writerow({
				'Bólkur': bev['Bólkur'],
				'Undir-Bólkur': bev['Undir-Bólkur'],
				'Navn': bev['Navn'],
				'Innihald': bev['Innihald'],
				'Styrki': bev['Styrki'],
				'Prísur': bev['Prísur'],
				'Alk/kr': bev['Alk/kr']
			})







	









	
