# confluence / jira automation utility functions

import requests
import urllib3
import json
import datetime
import base64
import os
import sys
from bs4 import BeautifulSoup
from html import escape
from html.parser import HTMLParser

urllib3.disable_warnings()

# General Utilities Class
class bUtils:

	def __init__(self, ConfigDictPath, LogPath):
		self.ConfigDict = json.loads(open(ConfigDictPath, "r").read())
		self.LogPath = LogPath
		self.Log("debug", "Class Entry: bUtils")

	def Log(self, level, message):
		# Main Logging Function
		if(not os.path.exists(self.LogPath)):
			f = open(self.LogPath, "w+")
			f.write("Log Creation: " + str(datetime.datetime.now()) + "\n")
			f.close()

		global_level = self.ConfigDict["Development"]["Verbosity"]
		logtime = str(datetime.datetime.now())

		loglevels = {
			"debug": "[d] " + logtime + " - " + message,
			"success":  "[+] " + logtime + " - " + message,
			"error": "[!] " + logtime + " - " + message,
			"info": "[?] " + logtime + " - " + message,
		}

		if(level == "debug"):
			if(global_level == "3"):
				open(self.LogPath, "a").write(loglevels[level] + "\n")
				print(loglevels[level])
				return loglevels[level]
			else:
				return
		elif(level == "info"):
			if(global_level in ["2", "3"]):
				open(self.LogPath, "a").write(loglevels[level] + "\n")
				print(loglevels[level])
				return loglevels[level]
			else:
				return
		elif(level == "success"):
			if(global_level in ["1", "2", "3"]):
				open(self.LogPath, "a").write(loglevels[level] + "\n")
				print(loglevels[level])
				return loglevels[level]
		else: # default, only error messages
			open(self.LogPath, "a").write(loglevels[level] + "\n")
			print(loglevels[level])
			return loglevels[level]

	def getErrorDetails(self, exceptione):
		# display exception file and line
		try:
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			fileline = str(exc_type) + "," + str(fname) + "," + str(exc_tb.tb_lineno)
			errorline = "[" + str(exceptione) + "\nInfo: " + fileline + "]"

			return errorline
		except: 
			self.Log("error", "[FATAL ERROR] (bUtils.getErrorDetails) ERROR ON ERROR WTF!")

	def GenerateBasicAuthHeader(self):
		# Generates the Basic Authorization header
		self.Log("debug", "Function Entry: bUtils.GenerateBasicAuthHeader")

		Username = self.ConfigDict["Basics"]["CUser"]
		Password = self.ConfigDict["Basics"]["CPass"]

		AuthHeader = {
			"Authorization": "Basic " + base64.b64encode( (Username + ":" + Password).encode() ).decode()
		}

		return AuthHeader

	def GenerateProxyInfo(self):
		self.Log("debug", "Function Entry: bUtils.GenerateProxyInfo")

		ProxyInfo = self.ConfigDict["Basics"]["proxy"]
		if(ProxyInfo["use"].lower() == "true"):
			ProxyInfo = ProxyInfo.pop("use")
		else:
			ProxyInfo = {}

		return ProxyInfo

	def GetPageVersion(self, PageID):
		# get confluence page version 
		self.Log("debug", "Function Entry: bUtils.GetPageVersion")

		BaseUrl = self.ConfigDict["Basics"]["Confluence_BaseURL"]

		AuthHeader = self.GenerateBasicAuthHeader()

		try:
			res = requests.get(BaseUrl + "/rest/api/content/" + PageID + "?expand=version", headers=AuthHeader, proxies=self.GenerateProxyInfo(), verify=False)

			PageInfoDict = json.loads(res.text)
			VersionNumber = PageInfoDict["version"]["number"]

			self.Log("success", "Retrieved version number (" + str(VersionNumber) + ") for page: " + PageID)
			return VersionNumber
		except Exception as e:
			self.Log("error", "(bUtils.GenerateBasicAuthHeader) Unable to retrieve version number for PageID: " + PageID)
			self.Log("error", "(bUtils.GenerateBasicAuthHeader) Details: " + self.getErrorDetails(e))
			return -1

	def UpdatePageBody(self, PageID, PageTitle, NewBody):
		#update confluence page body
		self.Log("debug", "Function Entry: bUtils.UpdatePageBody")

		try:
			CurrentVersion = self.GetPageVersion(PageID)
			if(CurrentVersion == -1):
				self.Log("error", "(bUtils.UpdatePageBody) Unable to update page body for PageID " + PageID + " due to issue retrieving page version")
				return 0

			NextVersion = int(CurrentVersion) + 1

			UpdateJSON = """
			{
				"type": "page",
				"title": "||PAGETITLE||",
				"version": {
					"number": ||NEXTVERSION||
				},
				"body": {
					"storage": {
						"value": "||NEWHTML||",
						"representation": "storage"
					}
				}
			}"""

			UpdateJSON = UpdateJSON.replace("||NEXTVERSION||", str(NextVersion))
			UpdateJSON = UpdateJSON.replace("||NEWHTML||", NewBody)
			UpdateJSON = UpdateJSON.replace("||PAGETITLE||", PageTitle)

			UpdateJSON = json.loads(UpdateJSON)
			FormattedJSON = json.dumps(UpdateJSON, indent=2)

			AuthHeader = self.GenerateBasicAuthHeader()
			AuthHeader["Content-Type"] = "application/json"

			BaseUrl = self.ConfigDict["Basics"]["Confluence_BaseURL"]

			res = requests.put(BaseUrl + "/rest/api/content/" + PageID +"?expand=body.storage", headers=AuthHeader, data=FormattedJSON, proxies=self.GenerateProxyInfo(), verify=False)

			if(res.status_code == 200):
				self.Log("success", "Successfully updated Page..")
				return 1
		except Exception as e:
			self.Log("error", "(bUtils.UpdatePageBody) Unable to update page body for PageID: " + PageID)
			self.Log("error", "(bUtils.UpdatePageBody) Details: " + self.getErrorDetails(e))

			return 0

	def GetChildPageIDsandTitles(self, PageID):
		#get page ids and titles for children pages of parent page:
		self.Log("debug", "Function Entry: bUtils.GetChildPageIDsandTitles")
		
		try:
			BaseUrl = self.ConfigDict["Basics"]["Confluence_BaseURL"]
			AuthHeader = self.GenerateBasicAuthHeader()

			res = requests.get(BaseUrl + "/rest/api/content/" + PageID + "/child?expand=page&limit=1000", headers=AuthHeader, proxies=self.GenerateProxyInfo(), verify=False)

			ChildPagesDict = json.loads(res.text)

			ChildPages = ChildPagesDict["page"]["results"]

			PageIDsandTitles = []
			for Page in ChildPages:
				PageIDsandTitles.append([Page["id"], Page["title"]])

			self.Log("success", "Successfully retrieved all child page IDs and Titles for Parent Page: " + PageID)
			return PageIDsandTitles
		except Exception as e:
			self.Log("error", "(bUtils.GetChildPageIDsandTitles) Unable to retrieve child pages from parent page: " + PageID)
			self.Log("error", "(bUtils.GetChildPageIDsandTitles) Details: " + self.getErrorDetails(e))
			return -1

	def ConvertYYYYMMDDtoDate(self, Date):
		# convert a YYYYMMDD date string to a datetime object
		self.Log("debug", "Function Entry: bUtils.ConvertYYYYMMDDtoDate")

		try:
			Year = Date[0:4]
			Month = Date[4:6]
			if(Month.startswith("0")):
				Month = Date[5]
			Day = Date[6:]
			if(Day.startswith("0")):
				Day = Date[6:][1]

			
			datetimeObj = datetime.datetime(int(Year), int(Month), int(Day))

			return datetimeObj
		except Exception as e:
			self.Log("error", "(bUtils.ConvertYYYYMMDDtoDate) Unable to convert str (" + Date + ") to datetime object")
			self.Log("error", '(bUtils.ConvertYYYYMMDDtoDate) Details: ' + self.getErrorDetails(e))
			return 0

	def ConvertDatetoYYYYMMDD(self, datetimeObj):
		# convert datetime object to YYYYMMDD str
		self.Log("debug", "Function Entry: bUtils.ConvertDatetoYYYYMMDD")

		try:
			YYYY = str(datetimeObj.year)
			MM = str(datetimeObj.month)
			if(len(MM) == 1):
				MM = "0" + MM
			DD = str(datetimeObj.day)
			if(len(DD) == 1):
				DD = "0" + DD

			return YYYY + MM + DD
		except Exception as e:
			self.Log("error", "(bUtils.ConvertDatetoYYYYMMDD) Unable to convert obj (" + datetimeObj + ") to YYYYMMDD str")
			self.Log("error", "(bUtils.ConvertDatetoYYYYMMDD) Details: " + self.getErrorDetails(e))
			return 0

	def CompareDatetimeObjects(self, CompareDatetime, CompareToDatetime):
		# Compare 2 datetime objects.
		# returns true = CompareDatetime is AFTER CompareToDatetime OR CompareDatetime == CompareToDatetime
		# returns false = CompareDatetime is BEFORE CompreToDatetime
		self.Log("debug", "Function Entry: bUtils.CompareDatetimeObjects")

		return CompareDatetime >= CompareToDatetime

	def GetPageHTML(self, PageId):
		# retrieve page html (body.storage)
		self.Log("debug", "Function Entry: bUtils.GetPageHTML")
		BaseUrl = self.ConfigDict["Basics"]["Confluence_BaseURL"]
		try:
			res = requests.get(BaseUrl + "/rest/api/content/" + PageId + "?expand=body.storage", headers=self.GenerateBasicAuthHeader(), proxies=self.GenerateProxyInfo(), verify=False)
			pagedict = json.loads(res.text)
			macro_html = pagedict["body"]["storage"]["value"]

			return macro_html.replace('\\"', '"')
		except Exception as e:
			self.Log("error", "(bUtils.GetPageHTML) Unable to retrieve page body.storage for page: " + PageId)
			self.Log("error", "(bUtils.GetPageHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetSoupFromFile(self, FilePath):
		# return beautifulsoup html object from html in a file
		self.Log("debug", "Function Entry: bUtils.GetSoupFromFile")

		try:
			return BeautifulSoup(open(FilePath).read(), "html.parser")
		except Exception as e:
			self.Log("error", "(bUtils.GetSoupFromFile) Unable to convert file (" + str(FilePath) + ") to soup object")
			self.Log("error", "(bUtils.GetSoupFromFile) Details: " + self.getErrorDetails(e))
			return 0

	def GetSoupFromStr(self, HTMLstr):
		# return beautifulsoup html object from html string
		self.Log("debug", "Function Entry: bUtils.GetSoupFromStr")

		try:
			return BeautifulSoup(HTMLstr, "html.parser")
		except Exception as e:
			self.Log("error", "(bUtils.GetSoupFromStr) Unable to convert string to soup object")
			self.Log("error", "(bUtils.GetSoupFromStr) Details: " + self.getErrorDetails(e))
			return 0

	def GetDatePickersFromHTML(self, soupobj):
		# grab live date picker object titles + settings from beautiful soup object
		self.Log("debug", "Function Entry: bUtils.GetDatePickersFromHTML")

		try:
			DatePickerCompleteObjects = soupobj.find_all('ac:structured-macro', attrs={"ac:name": "date-picker"})
			
			DatePickers = []

			for DatePickerObj in DatePickerCompleteObjects:
				DatePickerTitle = DatePickerObj.find('ac:parameter', attrs={"ac:name": "Title"}).text
				DatePickerDate = DatePickerObj.find('ac:parameter', attrs={"ac:name": "Data"}).text.split("=")[1]
				
				DatePickers.append([DatePickerTitle, DatePickerDate])

			return DatePickers
		except Exception as e:
			self.Log("error", "(bUtils.GetDatePickersFromHTML) Unable to retrieve date pickers from html")
			self.Log("error", "(bUtils.GetDatePickersFromHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetDropDownListsFromHTML(self, soupobj):
		# get drop down list titles + definitions from html
		self.Log("debug", "Function Entry: bUtils.GetDropDownListsFromHTML")

		try:
			DropDownListObjs = soupobj.find_all('ac:structured-macro', attrs={"ac:name": "lim-dropdown-list-v3"})			

			DropDownLists = []
			for DropDownListObj in DropDownListObjs:
				DropDownListTitle = DropDownListObj.find('ac:parameter', attrs={"ac:name": "Title"}).text
				DropDownListValue = DropDownListObj.find('ac:parameter', attrs={"ac:name": "Data"}).text.split("=")[1]

				DropDownLists.append([DropDownListTitle, DropDownListValue])

			return DropDownLists
		except Exception as e:
			self.Log("error", "(bUtils.GetDatePickersFromHTML) Unable to retrieve dropdown lists from html")
			self.Log("error", "(bUtils.GetDatePickersFromHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetTablesFromHTML(self, soupobj):
		# retrieve tables from HTML and return them as dictionairies
		self.Log("debug", "Function Entry: bUtils.GetTableFromHTML")

		try:
			TableObjs = soupobj.find_all('ac:structured-macro', attrs={"ac:name": "lim-table"})			
			TableDicts = {}
			i = 0 
			for TableObj in TableObjs:
				TableId = "Table_" + str(i)
				TableDicts[TableId] = {}

				TableRows = TableObj.find_all("tr")
				TableHeaders = TableObj.find_all("th")
				for THindex in range(len(TableHeaders)):
					TableHeaders[THindex] = TableHeaders[THindex].text
				
				TableDicts[TableId]["Headers"] = TableHeaders

				TableRowColumns = {}
				for TableRowindex in range(len(TableRows)):
					TableRow = TableRows[TableRowindex]
					RowId = "Row_" + str(TableRowindex)
					TableRowColumns[RowId] = []

					HTMLRowColumns = TableRow.find_all("td")
					for HTMLRowColumn in HTMLRowColumns:
						BulletedListbool = False
						ColumnText = HTMLRowColumn.find_all("li")
						if(ColumnText != []):
							BulletedListbool = True
						else:
							ColumnText = HTMLRowColumn.find_all("p")

						if(BulletedListbool):
							NewColText = ""
							for LIindex in range(len(ColumnText)):
								NewColText = NewColText + str(ColumnText[LIindex]).replace('"', '\\"')
							ColumnText = NewColText

						else:
							try:
								ColumnText = str(ColumnText[0]).replace('"', '\\"')
							except:
								ColumnText = HTMLRowColumn.text if len(HTMLRowColumn.text) > 1 else "None"

						
						TableRowColumns[RowId].append(ColumnText)

				TableDicts[TableId]["Rows"] = TableRowColumns
				del TableDicts[TableId]["Rows"]["Row_0"] # Row_0 is header row
				i += 1

			return TableDicts
				
		except Exception as e:
			self.Log("error", "(bUtils.GetTableFromHTML) Unable to retrieve tables from html")
			self.Log("error", "(bUtils.GetTableFromHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetTextAreasFromHTML(self, soupobj):
		# Get text area titles and definitions from html
		self.Log("debug", "Function Entry: bUtils.GetTextBoxesFromHTML")

		try:
			TextAreaObjs = soupobj.find_all('ac:structured-macro', attrs={"ac:name": "text-area"})			

			TextAreas = []
			for TextAreaObj in TextAreaObjs:
				#print(TextAreaObj)
				TextAreaTitle = TextAreaObj.find('ac:parameter', attrs={"ac:name": "Title"}).text
				TextAreaBody = TextAreaObj.find('ac:rich-text-body').text
				
				TextAreas.append([TextAreaTitle, TextAreaBody])

			return TextAreas
		except Exception as e:
			self.Log("error", "(bUtils.GetTextBoxesFromHTML) Unable to retrieve text areas from html")
			self.Log("error", "(bUtils.GetTextBoxesFromHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetTextFieldsFromHTML(self, soupobj):
		# Get text area titles and definitions from html
		self.Log("debug", "Function Entry: bUtils.GetTextFieldsFromHTML")

		try:
			TextFieldObjs = soupobj.find_all('ac:structured-macro', attrs={"ac:name": "lim-text-input"})			

			TextFields = []
			for TextFieldObj in TextFieldObjs:
				#print(TextAreaObj)
				TextFieldTitle = TextFieldObj.find('ac:parameter', attrs={"ac:name": "Title"}).text
				TextFieldBody = TextFieldObj.find('ac:plain-text-body')
				
				TextFields.append([TextFieldTitle, TextFieldBody])

			return TextFields
		except Exception as e:
			self.Log("error", "(bUtils.GetTextFieldsFromHTML) Unable to retrieve text fields from html")
			self.Log("error", "(bUtils.GetTextFieldsFromHTML) Details: " + self.getErrorDetails(e))
			return 0

	def GetAverageEffortCost(self, EffortCostList):
		# get the average effort cost based on a list of effort cost strings, return effort cost string and indicator
		self.Log("debug", "Function Entry: bUtils.GetAverageEffortCost")
		try:
			Tot = 0

			EffortDefinitions = {
				"Unclear": 0.0,
				"Low": 1.0,
				"Medium-Low": 2.0,
				"Medium": 3.0,
				"Medium-High": 4.0,
				"High": 5.0
			}

			for EffortCost in EffortCostList:
				Tot += EffortDefinitions[EffortCost]

			EffortIndicator = Tot/len(EffortCostList)
			EffortCost = None
			for EffortDef in EffortDefinitions:
				if(round(EffortIndicator) == EffortDefinitions[EffortDef]):
					EffortCost = EffortDef

			return [EffortDef, EffortIndicator]
		except Exception as e:
			self.Log("error", "(bUtils.GetAverageEffortCost) Unable to get the average of provided effort costs")
			self.Log("error", "(bUtils.GetAverageEffortCost) Details: " + self.getErrorDetails(e))
			return 0

	def GenerateTableOnHTML(self, TableContainerTypeandTitle, TableReplaceMes, TableData, PageHTML):
		# generate HTML table on the PageHTML page for a table that contains the TableReplaceMes
		# TableContainerTypeandTitle - the overarching container that holds the table. [container type, container title]
		#	containers can be the following types:
		#	- expand
		#	- panel
		# TableReplaceMes - the ReplaceMe strings that help identify the table on the page
		# TableData - a list of lists, each list is 1 row on the table
		# PageHTML - the HTML to write the table to

		# NOTE: THIS FUNCTION ONLY GENERATES TABLES WITH 4 COLUMNS CURRENTLY.
		# TODO: GENERATE TABLES WITH CUSTOM AMOUNTS OF COLUMNS
		self.Log("debug", "Function Entry: bUtils.GenerateTableOnHTML")
		try:
			soup = self.GetSoupFromStr(PageHTML)
		except Exception as e:
			self.Log("error", "(bUtils.GenerateTableOnHTML) Unable to generate soup object from provided PageHTML string")
			self.Log("error", "(bUtils.GenerateTableOnHTML) Details: " + self.getErrorDetails(e))
			return 0

		try:
			ContainerTypes = {
				"expand": ["ac:structured-macro", "expand"],
				"panel": ["ac:structured-macro", "panel"],
			}

			IndicatedContainerType = TableContainerTypeandTitle[0]
			IndicatedContainerTitle = TableContainerTypeandTitle[1]

			TableContainerTagType = ContainerTypes[IndicatedContainerType][0]
			TableContainerMacroType = ContainerTypes[IndicatedContainerType][1]
			TableContainers = soup.find_all(TableContainerTagType, attrs={"ac:name": TableContainerMacroType})

			for TableContainer in TableContainers:
				ExpansionParameters = TableContainer.find_all("ac:parameter")

				CorrectContainer = False
				for ExpansionParameter in ExpansionParameters:
					if(IndicatedContainerTitle == ExpansionParameter.text):
						CorrectContainer = True
				
				if CorrectContainer: # we have found the container we want to work on
					Tables = TableContainer.find_all("table", attrs={"class":"wrapped"})
					for Table in Tables:
						TableReplaceMeTags = Table.find_all("td")
						FoundTableReplaceMes = []
						for TableReplaceMeTag in TableReplaceMeTags:
							FoundTableReplaceMes.append(TableReplaceMeTag.text)
						
						if(len(TableReplaceMes) == len(FoundTableReplaceMes)): # for some reason doing TableReplaceMes == FoundTableReplaceMes doesn't work...
							MatchingReplaceMes = 0
							TotalReplaceMes = len(TableReplaceMes)
							for ReplaceMe in TableReplaceMes:
								if ReplaceMe in FoundTableReplaceMes:
									MatchingReplaceMes += 1

							if(MatchingReplaceMes == TotalReplaceMes): # found exact table we need
								TableRows = Table.find_all("tr")
								for TableRow in TableRows:
									HeaderRow = False
									if TableRow.find_all("th") == None or TableRow.find_all("th") == []: # ignore header row
										Columns = TableRow.find_all("td")
										for Column in Columns:
											if "||" in Column.text:
												HeaderRow = True
									if HeaderRow:
										TableRow.extract() # remove ReplaceMes

								TableBody = Table.find_all("tbody")[0]
								onerow = False

								for DataItem in TableData:
									Column_0 = self.FixHTML(DataItem[0])
									Column_1 = self.FixHTML(DataItem[3])
									Column_2 = self.FixHTML(DataItem[4])
									Column_3 = self.FixHTML(DataItem[5])

									NewRow = soup.new_tag("tr")
									
									NewColumn_0 = soup.new_tag(name="td", colspan=1)
									NewColumn_0.append(Column_0)
									NewRow.append(NewColumn_0)
									
									NewColumn_1 = soup.new_tag(name="td", colspan=1)
									NewColumn_1.append(Column_1)
									NewRow.append(NewColumn_1)
									
									NewColumn_2 = soup.new_tag(name="td", colspan=1)
									NewColumn_2.append(Column_2)
									NewRow.append(NewColumn_2)
									
									NewColumn_3 = soup.new_tag(name="td", colspan=1)
									NewColumn_3.append(Column_3)
									NewRow.append(NewColumn_3)
									

									Table.append(NewRow)

					Table = self.FixHTML(Table)
								#Table.append(TableBody)
		#	print(soup)
			return str(soup).replace("&lt;", "<").replace("&gt;", ">")
		except Exception as e:
			self.Log("error", "(bUtils.GenerateTableOnHTML) Unable to build out table")
			self.Log("error", "(bUtils.GenerateTableOnHTML) Details: " + self.getErrorDetails(e))
			return 0

	def FixHTML(self, HTMLItem):
		# fix html to make it usable for adding to pages
		self.Log("debug", "Function Entry: bUtils.FixHTML")

		RefinedHTML = ""

		if(type(HTMLItem) == type([])):
			for item in HTMLItem:
				item = str(item).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
				RefinedHTML = RefinedHTML + item + "\n"
		else:
			RefinedHTML = str(HTMLItem).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

		RefinedHTML = RefinedHTML.replace("&lt;", "<")
		return RefinedHTML						

	def UploadPageAsChild(self, PageHTML, PageTitle, ParentPageId):
		# upload a page as a child of another page
		self.Log("debug", "Function Entry: bUtil.UploadPageAsChild")
		try:
			AuthHeader = self.GenerateBasicAuthHeader()
			AuthHeader["Content-Type"] = "application/json"
			BaseUrl = self.ConfigDict["Basics"]["Confluence_BaseURL"]

			POSTJsonDict = {
				"type": "page",
				"title": PageTitle,
				"space": {
					"key": self.ConfigDict["Basics"]["Space_Key"]
				},
				"ancestors": [
					{
						"id": ParentPageId
					}
				],
				"body": {
					"storage": {
						"value": PageHTML,
						"representation": "storage"
					}
				}
			}

			POSTJson = json.dumps(POSTJsonDict)

			res = requests.post(BaseUrl + "/rest/api/content", headers=AuthHeader, data=POSTJson, proxies=self.GenerateProxyInfo(), verify=False)

			if(res.status_code != 200):
				self.Log("error", "(bUtil.UploadPageAsChild) Got Status Code: " + str(res.status_code))
				self.Log("error", "(bUtil.UploadPageAsChild) response message: \n" + res.text)
				return 0

			return res.status_code
		except Exception as e:
			self.Log("error", "(bUtil.UploadPageAsChild) Unable to upload page as child of Page: " + ParentPageId)
			self.Log("error", "(bUtil.UploadPageAsChild) Details: " + self.getErrorDetails(e))
			return 0

	def GenerateJiraTicket(self, TicketInformation):
		# Generate a Jira ticket
		# TicketInformation: [Title, Labels, Original Worktime Estimate, Description]
		self.Log("debug", "Function Entry: bUtil.GenerateJiraTicket")
		try:
			Title = TicketInformation[0]
			Labels = TicketInformation[1] # list
			OriginalWorktimeEstimate = TicketInformation[2]
			Description = TicketInformation[3]

			TicketDict = {
				"fields": {
					"project": {
						"key": self.ConfigDict["Basics"]["Jira_ProjectKey"]
					},
					"summary": Title,
					"description": Description,
					"labels": Labels,
					"timetracking": {
 						"originalEstimate": OriginalWorktimeEstimate
					},
					"issuetype": {
						"name": "Story"
					}
				}
			}

			TicketJson = json.dumps(TicketDict)

			HeaderDict = self.GenerateBasicAuthHeader()
			HeaderDict["Content-Type"] = "application/json"

			resp = requests.post(self.ConfigDict["Basics"]["Jira_BaseURL"] + "/rest/api/2/issue/", headers=HeaderDict, data=TicketJson, proxies=self.GenerateProxyInfo(), verify=False)
			
			if(resp.status_code in range(200,299)):
				print(resp.text)
				responsedict = json.loads(resp.text)
				self.Log("success", "Created Jira Ticket: " + responsedict["key"])
				return responsedict["key"]
			else:
				return 0

		except Exception as e:
			self.Log("error", "(bUtil.GenerateJiraTicket) Unable to generate Jira ticket")
			self.Log("error", "(bUtil.GenerateJiraTicket) Details: " + self.getErrorDetails(e))
			return 0

	def GetConfluencePageLabels(self, PageId):
		# get page labels from confluence page
		self.Log("debug", "Function Entry: bUtil.GetConfluencePageLabels")
		try:
			AuthHeader = self.GenerateBasicAuthHeader()

			ConfluenceURL = self.ConfigDict["Basics"]["Confluence_BaseURL"] + "/rest/api/content/" + PageId + "/label"
			Response = requests.get(ConfluenceURL, headers=AuthHeader, proxies=self.GenerateProxyInfo(), verify=False).text

			ResponseDict = json.loads(Response)
			ResponseDictLabelArr = ResponseDict["results"]

			PageLabels = []

			for LabelDict in ResponseDictLabelArr:
				Label = LabelDict["name"]
				PageLabels.append(Label)

			return PageLabels

		except Exception as e:
			self.Log("error", "(bUtil.GetConfluencePageLabels) Unable to get labels from page: " + PageId)
			self.Log("error", "(bUtil.GetConfluencePageLabels) Details: " + self.getErrorDetails(e))
			return 0

	def MoveConfluencePage(self, orgPageId, tgtPageTitle):
		# moves confluence page orgPageId to be child of page tgtPageTitle
		self.Log("debug", "Function Entry: bUtil.MoveConfluencePage")

		try:

			SpaceKey = self.ConfigDict["Basics"]["Space_Key"]

			AuthHeader = self.GenerateBasicAuthHeader()
			AuthHeader["x-atlassian-token"] = "no-check" # required by confluence

			ConfluenceURL = self.ConfigDict["Basics"]["Confluence_BaseURL"] + "/pages/movepage.action?pageId=" + str(orgPageId) + "&spaceKey=" + SpaceKey + "&targetTitle=" + str(tgtPageTitle) + "&position=append"

			response = requests.get(ConfluenceURL, headers=AuthHeader, proxies=self.GenerateProxyInfo(), verify=False)


			if(response.status_code in range(200, 299)):
				return 1
			else:
				return 0

		except Exception as e:
			self.Log("error", "(bUtil.MoveConfluencePage) Unable to move page " + str(orgPageId) + " to be child of: " + str(tgtPageTitle))
			self.Log("error", "(bUtil.MoveConfluencePage) Details: " + self.getErrorDetails(e))
			return 0

