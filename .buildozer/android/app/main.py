# #############################################################################
#
#  main.py - main entry point for buckshotApp
#   largely copied from native python program 'buckshot'
#    (github.com/ncssar/buckshot)
#   Given a set of ambiguous coordinate numbers, make gpx markers
#   for all possibilities in all three lat-lon coordinate systems
#
#
#   buckshot is developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2015 Tom Grundy
#
#   buckshotApp (c) 2019 Tom Grundy, using kivy and buildozer
#
#  http://github.com/ncssar/buckshotApp
#
#  Contact the author at nccaves@yahoo.com
#   Attribution, feedback, bug reports and feature requests are appreciated
#
#  REVISION HISTORY
#-----------------------------------------------------------------------------
#   DATE   | AUTHOR | VER |  NOTES
#-----------------------------------------------------------------------------
#   1-2-19    TMG     1.0   First version working for Android (unpublished)
#
# #############################################################################

__version__ = '1.0'

# perform any calls to Config.set before importing any kivy modules!
# (https://kivy.org/docs/api-kivy.config.html)
from kivy.config import Config
Config.set('kivy','keyboard_mode','system')
Config.set('kivy','log_dir','buckshotLogDir')
Config.set('kivy','log_enable',1)
Config.set('kivy','log_level','info')
Config.set('kivy','log_maxfiles',5)
# Config.set('kivy','window_icon','target.ico')

import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from kivy.core.window import Window
from kivy.uix.widget import Widget

from kivy.adapters.dictadapter import DictAdapter
from kivy.uix.selectableview import SelectableView
from kivy.uix.listview import ListView, ListItemButton
from kivy.adapters.listadapter import ListAdapter
from kivy.adapters.models import SelectableDataItem
from kivy.uix.gridlayout import GridLayout
from kivy.lang import Builder
from kivy.factory import Factory
from kivy.logger import Logger
from kivy.utils import platform

import xml.dom.minidom
# import regex as re
import re
from parse import *
import sys
# import requests
import json
import os

from jnius import cast
from jnius import autoclass

exactMatchPrefix="*"
closeMatchPrefix="+"

Factory.register('SelectableView', cls=SelectableView)
Factory.register('ListItemButton', cls=ListItemButton)

# from kivy/examples/widgets/lists/fixtures.py:
# A dictionary of dicts, with only the minimum required is_selected attribute,
# for use with examples using a simple list of integers in a list view.
integers_dict = {str(i): {'text': str(i), 'is_selected': False}
                 for i in range(100)}

# Builder.load_string(
# [CustomListItem@SelectableView+BoxLayout]:
#     size_hint_y: ctx.size_hint_y
#     height: ctx.height
#     ListItemButton:
#         text: ctx.text
#         is_selected: ctx.is_selected
#     BoxLayout:
#         orientation: "vertical"
#         Label:
#             id: coordsEntryField
#             size_hint_y: 0.15
#             markup: True
#             text: "Coords"
#             halign: "left"
#         Label:
#             id: labelField
#             text: "Enter or paste original 'coordinates' here.  Any non-digit characters will be ignored."
#         BoxLayout:
#             id: buttonBoxLayout
#             orientation: "horizontal"
#             Button:
#                 text: "View List"
#                 on_release: root.manager.viewList
#             Button:
#                 text: "Map It"
#                 on_release: root.manager.mapIt
#             Widget:
#                 # placeholder for the keypad
#                 size_hint_y: 0.5  
# )

class DataItem(SelectableDataItem):
    def __init__(self, name, **kwargs):
        self.name = name
        super(DataItem, self).__init__(**kwargs)       

class BuckshotApp(App):
    def coordsChanged(self,*args):
        Logger.info("typing:"+self.coordsField.text)
        self.calcLatLon()

    def go(self,*args):
        self.coords=self.coordsField.text
        Logger.info("button clicked:"+self.coords)
        Logger.info("writing GPX:"+str(self.writeGPX()))    


# begin copy and modify-as-needed from buckshot.py 4-16-17:

    #fnameValidate: try writing a test file to the specified filename;
    # return the filehandle if valid, or print the error message and return False
    # if invalid for whatever reason
    def fnameValidate(self,filename):
        try:
            f=open(filename,"w")
        except (IOError,FileNotFoundError) as err:
#             QMessageBox.warning(self,"Invalid Filename","GPX filename is not valid:\n\n"+str(err)+"\n\nNo markers written to GPX or URL.  Fix or blank out the filename, and try again.")
            Logger.warning("Sorry, filename "+filename+" is not valid.")
            return False
        else:
            return f
        
    def createMarkers(self,*args):
        print("createMarkers called")
        
        # if a gpx filename is specified, validate it first; if invalid, force
        #  the user to fix it or blank it out before generating any URL markers

#         if not self.fnameValidate(self.ui.gpxFileNameField.text()):
        if not self.fnameValidate(self.gpxFileName):
            return
            
        DdIdx=0
        DMmIdx=0
        DMSsIdx=0
        DdIdxFlag=len(self.coordDdStringList)>1
        DMmIdxFlag=len(self.coordDMmStringList)>1
        DMSsIdxFlag=len(self.coordDMSsStringList)>1

#         markerName=self.ui.markerNameField.text()
        markerName="buckshotAppTest"
        if markerName=="":
            markerName="X"

        # for exact match, use a ring with center dot
        # for close match, use a hollow ring
        # appropriate prefixes were determined from decoding json POST request
        #  of a live header when creating each type of marker by hand
        # final URL values:
        #  simple dot: "#<hex_color>"
        #  target: "c:target,<hex_color>" (notice, no pound sign)
        #  ring: "c:ring,<hex_color>" (notice, no pound sign)
        exactUrlPrefix="c:target,"
        closeUrlPrefix="c:ring,"

        # build a list of markers; each marker is a list:
        # [markerName,lat,lon,color]
        markerList=[]
        for DdString in self.coordDdStringList:
            DdIdx=DdIdx+1
            prefix=""
            urlPrefix="#"
#             if DdString.startswith(exactMatchPrefix):
            if DdString==self.bestMatch:
                DdString=DdString.replace(exactMatchPrefix,"")
                prefix=exactMatchPrefix
                urlPrefix=exactUrlPrefix
            if DdString.startswith(closeMatchPrefix):
                DdString=DdString.replace(closeMatchPrefix,"")
                prefix=closeMatchPrefix
                urlPrefix=closeUrlPrefix
            print("  Dd : '"+DdString+"'")
            r=parse("{:g}deg N x {:g}deg W",DdString)
            print(r)
            if DdIdxFlag:
                idx=str(DdIdx)
            else:
                idx=""
            markerList.append([prefix+markerName+"_Dd"+idx,r[0],-r[1],urlPrefix+"FF0000"])
        for DMmString in self.coordDMmStringList:
            DMmIdx=DMmIdx+1
            prefix=""
            urlPrefix="#"
#             if DMmString.startswith(exactMatchPrefix):
            if DMmString==self.bestMatch:
                DMmString=DMmString.replace(exactMatchPrefix,"")
                prefix=exactMatchPrefix
                urlPrefix=exactUrlPrefix
            if DMmString.startswith(closeMatchPrefix):
                DMmString=DMmString.replace(closeMatchPrefix,"")
                prefix=closeMatchPrefix
                urlPrefix=closeUrlPrefix
            print("  DMm : "+DMmString)
            r=parse("{:g}deg {:g}min N x {:g}deg {:g}min W",DMmString)
            print(r)
            if DMmIdxFlag:
                idx=str(DMmIdx)
            else:
                idx=""
            markerList.append([prefix+markerName+"_DMm"+idx,r[0]+r[1]/60.0,-(r[2]+r[3]/60.0),urlPrefix+"FF00FF"])
        for DMSsString in self.coordDMSsStringList:
            DMSsIdx=DMSsIdx+1
            prefix=""
            urlPrefix="#"
#             if DMSsString.startswith(exactMatchPrefix):
            if DMSsString==self.bestMatch:
                DMSsString=DMSsString.replace(exactMatchPrefix,"")
                prefix=exactMatchPrefix
                urlPrefix=exactUrlPrefix
            if DMSsString.startswith(closeMatchPrefix):
                DMSsString=DMSsString.replace(closeMatchPrefix,"")
                prefix=closeMatchPrefix
                urlPrefix=closeUrlPrefix
            print("  DMSs: "+DMSsString)
            r=parse("{:g}deg {:g}min {:g}sec N x {:g}deg {:g}min {:g}sec W",DMSsString)
            print(r)
            if DMSsIdxFlag:
                idx=str(DMSsIdx)
            else:
                idx=""
            markerList.append([prefix+markerName+"_DMSs"+idx,r[0]+r[1]/60.0+r[2]/3600.0,-(r[3]+r[4]/60.0+r[5]/3600.0),urlPrefix+"0000FF"])

        print("Final marker list:")
        print(str(markerList))

        if self.writeGPX(markerList):
            infoStr="\nWrote GPX?   YES"
        else:
            infoStr="\nWrote GPX?   NO"

#         if self.ui.URLField.text():
#             # the domain and port is defined as the URL up to and including the first slash
#             #  after the http:// if it exists, or just the first slash otherwise
#             url=self.ui.URLField.text()
#             domainAndPort=url.lower().replace("http://","").split("/")[0]
#             print("domainAndPort: "+domainAndPort)
#             s=requests.session()
#             try:
#                 s.get(url)
#             except:
#                 QMessageBox.warning(self,"URL Failed","Could not communicate with the specfied URL.  Fix it or blank it out, and try again.")
#                 infoStr+="\nWrote URL?   NO"
#             else:
#                 postErr=""
#                 for marker in markerList:
#                     if postErr=="":
#                         j={}
#                         j['label']=marker[0]
#                         j['folderId']=None
#                         j['url']=marker[3]
#                         j['comments']=""
#                         if marker[0].startswith(exactMatchPrefix):
#                             j['comments']="User-selected best match!"
#                         if marker[0].startswith(closeMatchPrefix):
#                             j['comments']="CLOSE match for specified coordinates"
#                         j['position']={"lat":marker[1],"lng":marker[2]}
#                         try:
#                             r=s.post("http://"+domainAndPort+"/rest/marker/",data={'json':json.dumps(j)})
#                         except requests.exceptions.RequestException as err:
#                             postErr=err
#                         else:
#                             print("DUMP:")
#                             print(json.dumps(j))
#                 if postErr=="":
#                     infoStr+="\nWrote URL?   YES"
#                 else:
#                     infoStr+="\nWrote URL?   NO"
#                     QMessageBox.warning(self,"URL Post Request Failed","URL POST request failed:\n\n"+str(postErr)+"\n\nNo markers written to URL.  Fix or blank out the URL field, and try again.")
#         else:
#             infoStr+="\nWrote URL?   NO"
#             print("No URL specified; skipping URL export.")
#             
#         QMessageBox.information(self,"Markers Created","Markers created successfully.\n"+infoStr)
        
    def writeGPX(self,markerList):
#         gpxFileName=self.ui.gpxFileNameField.text()
        Logger.info("Writing GPX file "+self.gpxFileName)
        Environment=autoclass('android.os.Environment')
        PythonActivity=autoclass('org.kivy.android.PythonActivity')
        mActivity=PythonActivity.mActivity
        Context=autoclass('android.content.Context')
        DownloadManager=autoclass('android.app.DownloadManager')
        mimetype="application/gpx+xml"

        # make sure the file is writable; if not, return False here
#         gpxFile=self.fnameValidate(self.gpxFileName)
#         if not gpxFile:
#             return False

        doc=xml.dom.minidom.Document()
        gpx=doc.createElement("gpx")
        gpx.setAttribute("creator","BUCKSHOT")
        gpx.setAttribute("version","1.1")
        gpx.setAttribute("xmlns","http://www.topografix.com/GPX/1/1")

        # each element in markerList will result in a gpx wpt token.
        #  markerList element syntax = [name,lat,lon,color]

        # <desc> CDATA contains SARSoft marker and color
        # <sym> CDATA contains Locus marker, parsed from marker name
        #  some relevant Locus markers:
        #   z-ico01 = red down arrow
        #   z-ico02 = red x
        #   z-ico03 = red donut
        #   z-ico04 = red dot
        #   z-ico05 = red down triangle
        #   same sequence as above: 06-10 = cyan; 11-15=green; 16-20=yellow
        #   misc-sunny = large green star bubble

        for marker in markerList:
##            print("marker:"+str(marker)+"\n")
            wpt=doc.createElement("wpt")
            wpt.setAttribute("lat",str(marker[1]))
            wpt.setAttribute("lon",str(marker[2]))
            name=doc.createElement("name")
            desc=doc.createElement("desc")
            sym=doc.createElement("sym")
            descCDATAStr="comments=&url=%23"+marker[3][1:]
            descCDATA=doc.createCDATASection(descCDATAStr)
            if "_Dd" in marker[0]:
                if marker[0].startswith(exactMatchPrefix):
                    symCDATAStr="z-ico01"
                else:
                    symCDATAStr="z-ico04"
            elif "_DMm" in marker[0]:
                if marker[0].startswith(exactMatchPrefix):
                    symCDATAStr="z-ico06"
                else:
                    symCDATAStr="z-ico09"
            elif "_DMSs" in marker[0]:
                if marker[0].startswith(exactMatchPrefix):
                    symCDATAStr="z-ico16"
                else:
                    symCDATAStr="z-ico19"
            else:
                if marker[0].startswith(exactMatchPrefix):
                    symCDATAStr="z-ico11"
                else:
                    symCDATAStr="z-ico14"

            name.appendChild(doc.createTextNode(marker[0]))
            desc.appendChild(descCDATA)
            symCDATA=doc.createCDATASection(symCDATAStr)
            sym.appendChild(symCDATA)
            wpt.appendChild(name)
            wpt.appendChild(desc)
            wpt.appendChild(sym)
            gpx.appendChild(wpt)

        doc.appendChild(gpx)

        save_dir_jfile=Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        save_dir=save_dir_jfile.getAbsolutePath()     
        Logger.info("external storage public directory: "+str(save_dir))
        
        path=save_dir+"/buckshot.gpx"
        try:
            f = open(path, "w")
        except PermissionError as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            PythonActivity.toastError("File not written: Permission denied\n\nPlease add Storage permission for this app using your device's Settings menu, then try again.\n\nYou should not need to restart the app.")
            PythonActivity.toastError("File not written: "+str(ex))
        except Exception as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            PythonActivity.toastError("File not written: "+str(ex))
        else:
            f.write(doc.toprettyxml())
            f.close()
            # create a completed download notification for the saved file
            DownloadService=mActivity.getSystemService(Context.DOWNLOAD_SERVICE)
            DownloadService.addCompletedDownload(path,path,True,mimetype,path,os.stat(path).st_size,True)    
            PythonActivity.toastError("File created successfully:\n\n"+path+"\n\nCheck your 'download' notifications for single-tap access.")

#         gpxFile.write(doc.toprettyxml())
#         gpxFile.close()
        return True


    def calcLatLon(self):

### code to get overlapping matches (i.e. each possible longitude whole number) and their indeces:
##import regex as re
##matches=re.finditer("1[012][0123456789]",numbers,overlapped=True)
##[match.span() for match in matches]

#         coordString=self.ui.coordsField.text()
        coordString=self.coordsField.text

        # shortCoordString = the 'canonical' form that the possibilities will
        #  be compared to, to check for close or exact matches.  Same as
        #  coordString, with standardized D/M/S delimiters; cannot eliminate all
        #  spaces at this point since they may or may not be important delimiters;
        #  therefore, will need to insert a space into the shortCoordString before
        #  longitude for each possibility on the fly during parsing; this ensures
        #  that original coordString with NO spaces at all can still make an
        #  exact match.

        shortCoordString=coordString.lower()
        shortCoordString=re.sub(r'[Xx]',' ',shortCoordString) # replace X or x with space for canonical form
        shortCoordString=re.sub(r'\s+',' ',shortCoordString) # get rid of duplicate spaces
        shortCoordString=re.sub(r'\'','m',shortCoordString)
        shortCoordString=re.sub(r'"','s',shortCoordString)
        Logger.info("Short coordinate string for comparison:"+shortCoordString+"\n")



        # different approach:
        # make a list of the indeces and kinds of delimiters;
        # if the indeces all match, it is a 'close' match;
        # if the indeces all match AND each one is of the same kind, it is an 'exact' match

        delimIter=re.finditer(r'[ .dDmMsS\'"-]+',coordString)
#         delimiter='.'



#        numbers=re.sub(r'[ .dDmMsS\'"-]','',coordString)
        numbers=re.sub(r'\D','',coordString)
#         numbers="123"
        print("Raw Numbers:"+numbers+"\n")

##        numbers=self.ui.numbersField.text()
        self.coordDdStringList=[]
        self.coordDMmStringList=[]
        self.coordDMSsStringList=[]
        latDegIndex=0
        lonDegIndex=-1
        # use the following line if the regex module is being used:
#         pattern=re.compile('1[012][0123456789]') # assume longitude 100-129 west
        # or use this line if the re module is being used (as in Kivy which doesn't build with regex):
#         pattern=re.compile('(?=(1[012][0123456789]))')
        matches=re.finditer('(?=(1[012][0123456789]))',numbers)
#         matches=pattern.finditer(numbers,2,overlapped=True) # this works with regex module only
#         matches=[]
#         Logger.info("matches:"+str([match.span() for match in matches])) # this line destroys matches!
        for lonDegMobj in matches:
            Logger.info("match:"+str(lonDegMobj.span()))
##        lonDegMobj=pattern.search(numbers,2) # skip the first two characters
##        if lonDegMobj!=None:
            lonDegIndex=lonDegMobj.start()
#             lonDeg=lonDegMobj.group()
            lonDeg=numbers[lonDegIndex:lonDegIndex+3]
            Logger.info("lonDegIndex: '"+str(lonDegIndex)+"'")
            Logger.info("Longitude Degrees: '"+lonDeg+"'")
            lonRestIndex=lonDegIndex+3
            lonRest=numbers[lonRestIndex:]
            Logger.info("Longitude rest: '"+lonRest+"'")
            if int(numbers[0])>1 and int(numbers[0])<5: #assume latitude 20-49 north
                latDeg=numbers[0:2]
                latRest=numbers[2:lonDegIndex]
                Logger.info("Latitude degrees: '"+latDeg+"'")
                Logger.info("Latitude rest: '"+latRest+"'")

                # initialize whole minutes and seconds to unrealizable values
                #  for use in the 'possible' section below
                latMin1="99"
                latMin2="99"
                latSec11="99"
                latSec12="99"
                latSec21="99"
                latSec22="99"

                lonMin1="99"
                lonMin2="99"
                lonSec11="99"
                lonSec12="99"
                lonSec21="99"
                lonSec22="99"

                # initialize "rest" arguments to blank strings
                latMin1Rest=""
                latMin2Rest=""
                latSec11Rest=""
                latSec12Rest=""
                latSec21Rest=""
                latSec22Rest=""

                lonMin1Rest=""
                lonMin2Rest=""
                lonSec11Rest=""
                lonSec12Rest=""
                lonSec21Rest=""
                lonSec22Rest=""

                # parse minutes and seconds from the rest of the string
                # whole minutes and whole seconds could be one digit or two digits
                if len(latRest)>0:
                    print("t1")
                    latMin1=latRest[0]
                    if len(latRest)>1:
                        print("t2")
                        latMin1Rest=latRest[1:]
                        latMin2=latRest[0:2]
                        if len(latRest)>2:
                            print("t2.5")
                            latMin2Rest=latRest[2:]
                        if len(latMin1Rest)>0:
                            print("t3")
                            latSec1=latMin1Rest[0:]
                            if len(latSec1)>0:
                                print("t4")
                                latSec11=latSec1[0]
                                if len(latSec1)>1:
                                    print("t5")
                                    latSec11Rest=latSec1[1:]
                                    latSec12=latSec1[0:2]
                                    if len(latSec1)>2:
                                        print("t5.5")
                                        latSec12Rest=latSec1[2:]
                                    if len(latMin2Rest)>0:
                                        print("t6")
                                        latSec2=latMin2Rest[0:]
                                        if len(latSec2)>0:
                                            print("t7")
                                            latSec21=latSec2[0]
                                            if len(latSec2)>1:
                                                print("t8")
                                                latSec21Rest=latSec2[1:]
                                                latSec22=latSec2[0:2]
                                                if len(latSec2)>2:
                                                    print("t9")
                                                    latSec22Rest=latSec2[2:]
                                else:
                                    latSec2="0" # account for implied zero seconds
                                    latSec21="0"
                        else:
                            latSec1="0" # account for implied zero seconds
                            latSec11="0"

                if len(lonRest)>0:
                    lonMin1=lonRest[0]
                    if len(lonRest)>1:
                        lonMin1Rest=lonRest[1:]
                        lonMin2=lonRest[0:2]
                        if len(lonRest)>2:
                            lonMin2Rest=lonRest[2:]
                        if len(lonMin1Rest)>0:
                            lonSec1=lonMin1Rest[0:]
                            if len(lonSec1)>0:
                                lonSec11=lonSec1[0]
                                if len(lonSec1)>1:
                                    lonSec11Rest=lonSec1[1:]
                                    lonSec12=lonSec1[0:2]
                                    if len(lonSec1)>2:
                                        lonSec12Rest=lonSec1[2:]
                                    if len(lonMin2Rest)>0:
                                        lonSec2=lonMin2Rest[0:]
                                        if len(lonSec2)>0:
                                            lonSec21=lonSec2[0]
                                            if len(lonSec2)>1:
                                                lonSec21Rest=lonSec2[1:]
                                                lonSec22=lonSec2[0:2]
                                                if len(lonSec2)>2:
                                                    lonSec22Rest=lonSec2[2:]
                                else:
                                    lonSec2="0" # account for implied zero seconds
                                    lonSec21="0"
                        else:
                            lonSec1="0" # account for implied zero seconds
                            lonSec11="0"


                # set flags as to which ones are possible
                # (whole min/sec <60 (2-digit) or <10 (1-digit))
                latMin1Possible=int(latMin1)<10
                latMin2Possible=int(latMin2)>9 and int(latMin2)<60
                latSec11Possible=int(latSec11)<10
                latSec12Possible=int(latSec12)<60
                latSec21Possible=int(latSec21)<10
                latSec22Possible=int(latSec22)<60

                lonMin1Possible=int(lonMin1)<10
                lonMin2Possible=int(lonMin2)>9 and int(lonMin2)<60
                lonSec11Possible=int(lonSec11)<10
                lonSec12Possible=int(lonSec12)<60
                lonSec21Possible=int(lonSec21)<10
                lonSec22Possible=int(lonSec22)<60

                print("latMin1Possible:"+str(latMin1Possible)+":"+latMin1+":"+latMin1Rest)
                print("latMin2Possible:"+str(latMin2Possible)+":"+latMin2+":"+latMin2Rest)
                print("latSec11Possible:"+str(latSec11Possible)+":"+latSec11+":"+latSec11Rest)
                print("latSec12Possible:"+str(latSec12Possible)+":"+latSec12+":"+latSec12Rest)
                print("latSec21Possible:"+str(latSec21Possible)+":"+latSec21+":"+latSec21Rest)
                print("latSec22Possible:"+str(latSec22Possible)+":"+latSec22+":"+latSec22Rest)

                print("lonMin1Possible:"+str(lonMin1Possible)+":"+lonMin1+":"+lonMin1Rest)
                print("lonMin2Possible:"+str(lonMin2Possible)+":"+lonMin2+":"+lonMin2Rest)
                print("lonSec11Possible:"+str(lonSec11Possible)+":"+lonSec11+":"+lonSec11Rest)
                print("lonSec12Possible:"+str(lonSec12Possible)+":"+lonSec12+":"+lonSec12Rest)
                print("lonSec21Possible:"+str(lonSec21Possible)+":"+lonSec21+":"+lonSec21Rest)
                print("lonSec22Possible:"+str(lonSec22Possible)+":"+lonSec22+":"+lonSec22Rest)

                # zero-pad right-of-decimal if needed, i.e. no blank strings right-of-decimal

                latRest=latRest or "0"
                lonRest=lonRest or "0"
                latMin1Rest=latMin1Rest or "0"
                latMin2Rest=latMin2Rest or "0"
                lonMin1Rest=lonMin1Rest or "0"
                lonMin2Rest=lonMin2Rest or "0"
                latSec11Rest=latSec11Rest or "0"
                latSec12Rest=latSec12Rest or "0"
                latSec21Rest=latSec21Rest or "0"
                latSec22Rest=latSec22Rest or "0"
                lonSec11Rest=lonSec11Rest or "0"
                lonSec12Rest=lonSec12Rest or "0"
                lonSec21Rest=lonSec21Rest or "0"
                lonSec22Rest=lonSec22Rest or "0"

                # build the lists of possible coordinate strings for each coordinate system
                #  (if only one of lat/lon per pair is possible, then the pair is
                #   not possible)

                self.coordDdStringList.append(str(latDeg+"."+latRest+"deg N x "+lonDeg+"."+lonRest+"deg W"))

                if latMin1Possible and lonMin1Possible:
                    self.coordDMmStringList.append(str(latDeg+"deg "+latMin1+"."+latMin1Rest+"min N x "+lonDeg+"deg "+lonMin1+"."+lonMin1Rest+"min W"))
                if latMin1Possible and lonMin2Possible:
                    self.coordDMmStringList.append(str(latDeg+"deg "+latMin1+"."+latMin1Rest+"min N x "+lonDeg+"deg "+lonMin2+"."+lonMin2Rest+"min W"))
                if latMin2Possible and lonMin1Possible:
                    self.coordDMmStringList.append(str(latDeg+"deg "+latMin2+"."+latMin2Rest+"min N x "+lonDeg+"deg "+lonMin1+"."+lonMin1Rest+"min W"))
                if latMin2Possible and lonMin2Possible:
                    self.coordDMmStringList.append(str(latDeg+"deg "+latMin2+"."+latMin2Rest+"min N x "+lonDeg+"deg "+lonMin2+"."+lonMin2Rest+"min W"))

                if latSec11Possible and lonSec11Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec11+"."+latSec11Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec11+"."+lonSec11Rest+"sec W"))
                if latSec11Possible and lonSec12Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec11+"."+latSec11Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec12+"."+lonSec12Rest+"sec W"))
                if latSec11Possible and lonSec21Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec11+"."+latSec11Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec21+"."+lonSec21Rest+"sec W"))
                if latSec11Possible and lonSec22Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec11+"."+latSec11Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec22+"."+lonSec22Rest+"sec W"))
                if latSec12Possible and lonSec11Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec12+"."+latSec12Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec11+"."+lonSec11Rest+"sec W"))
                if latSec12Possible and lonSec12Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec12+"."+latSec12Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec12+"."+lonSec12Rest+"sec W"))
                if latSec12Possible and lonSec21Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec12+"."+latSec12Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec21+"."+lonSec21Rest+"sec W"))
                if latSec12Possible and lonSec22Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin1+"min "+latSec12+"."+latSec12Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec22+"."+lonSec22Rest+"sec W"))
                if latSec21Possible and lonSec11Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec21+"."+latSec21Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec11+"."+lonSec11Rest+"sec W"))
                if latSec21Possible and lonSec12Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec21+"."+latSec21Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec12+"."+lonSec12Rest+"sec W"))
                if latSec21Possible and lonSec21Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec21+"."+latSec21Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec21+"."+lonSec21Rest+"sec W"))
                if latSec21Possible and lonSec22Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec21+"."+latSec21Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec22+"."+lonSec22Rest+"sec W"))
                if latSec22Possible and lonSec11Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec22+"."+latSec22Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec11+"."+lonSec11Rest+"sec W"))
                if latSec22Possible and lonSec12Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec22+"."+latSec22Rest+"sec N x "+lonDeg+"deg "+lonMin1+"min "+lonSec12+"."+lonSec12Rest+"sec W"))
                if latSec22Possible and lonSec21Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec22+"."+latSec22Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec21+"."+lonSec21Rest+"sec W"))
                if latSec22Possible and lonSec22Possible:
                    self.coordDMSsStringList.append(str(latDeg+"deg "+latMin2+"min "+latSec22+"."+latSec22Rest+"sec N x "+lonDeg+"deg "+lonMin2+"min "+lonSec22+"."+lonSec22Rest+"sec W"))
            else:
                print("Latitiude not found.")
        else:
            print("Longitude not found.")

#         self.ui.DdField.setPlainText("\n".join(self.coordDdStringList))
#         self.ui.DMmField.setPlainText("\n".join(self.coordDMmStringList))
#         self.ui.DMSsField.setPlainText("\n".join(self.coordDMSsStringList))
#         self.ui.DdField.clear()
#         self.ui.DdField.addItems(self.coordDdStringList)
#         self.ui.DMmField.clear()
#         self.ui.DMmField.addItems(self.coordDMmStringList)
#         self.ui.DMSsField.clear()
#         self.ui.DMSsField.addItems(self.coordDMSsStringList)

        # list view modification code taken from
        #  kivy/examples/lists/list_reset_data.py
#         if self.coordDdStringList!=[]:
        self.list_adapter.data=[]
        Logger.info("coordDdStringList:"+str(self.coordDdStringList))
        for DdString in self.coordDdStringList:
            item=DataItem(name=DdString)
            self.list_adapter.data.append(item)
#         if self.coordDMmStringList!=[]:
        for DMmString in self.coordDMmStringList:
            item=DataItem(name=DMmString)
            self.list_adapter.data.append(item)
#         if self.coordDMSsStringList!=[]:
        for DMSsString in self.coordDMSsStringList:
            item=DataItem(name=DMSsString)
            self.list_adapter.data.append(item)
            

        print("Possible Dd coordinates:\n"+str(self.coordDdStringList))
        print("Possible DMm coordinates:\n"+str(self.coordDMmStringList))
        print("Possible DMSs coordinates:\n"+str(self.coordDMSsStringList))

        # now find the 'short' string corresponding to each possibility, and
        #  see how close of a match it is to the originally entered string
        #  (highlight the row in the GUI, and change the marker name and symbol)
        for n,DdString in enumerate(self.coordDdStringList):
            DdShort=DdString.replace("deg ","d")
            DdShort=DdShort.replace("N x "," ")
            DdShort=DdShort.replace("W","")
            print("DdShort:"+DdShort)
            if DdShort==shortCoordString:
                print("  EXACT MATCH!")
                self.coordDdStringList[n]=exactMatchPrefix+DdString
#                 self.ui.DdField.setPlainText("\n".join(self.coordDdStringList))
#                 self.ui.DdField.clear()
#                 self.ui.DdField.addItems(self.coordDdStringList)

        for n,DMmString in enumerate(self.coordDMmStringList):
            DMmShort=DMmString.replace("deg ","d")
            DMmShort=DMmShort.replace("min ","m")
            DMmShort=DMmShort.replace("N x "," ")
            DMmShort=DMmShort.replace("W","")
            print("DMmShort:"+DMmShort)
            if DMmShort==shortCoordString:
                print("  EXACT MATCH!")
                self.coordDMmStringList[n]=exactMatchPrefix+DMmString
#                 self.ui.DMmField.setPlainText("\n".join(self.coordDMmStringList))
#                 self.ui.DMmField.clear()
#                 self.ui.DMmField.addItems(self.coordDMmStringList)

        for n,DMSsString in enumerate(self.coordDMSsStringList):
            DMSsShort=DMSsString.replace("deg ","d")
            DMSsShort=DMSsShort.replace("min ","m")
            DMSsShort=DMSsShort.replace("sec ","s")
            DMSsShort=DMSsShort.replace("N x "," ")
            DMSsShort=DMSsShort.replace("W","")
            print("DMSsShort:"+DMSsShort)
            if DMSsShort==shortCoordString:
                print("  EXACT MATCH!")
                self.coordDMSsStringList[n]=exactMatchPrefix+DMSsString
#                 self.ui.DMSsField.setPlainText("\n".join(self.coordDMSsStringList))
#                 self.ui.DMSsField.clear()
#                 self.ui.DMSsField.addItems(self.coordDMSsStringList)

        nDd=len(self.coordDdStringList)
        nDMm=len(self.coordDMmStringList)
        nDMSs=len(self.coordDMSsStringList)
        
        self.viewSwitchButton.text=("View List\n  D.d : "+str(nDd)+"\n DM.m : "+str(nDMm)+"\nDMS.s : "+str(nDMSs))
        
#     def createMarkers(self):

#     def viewSwitch(self,*args):
#         # note, the keyboard (if shown) is NOT a member of self.layout.children
#         if self.shown=="keyboard":
#             self.layout.remove_widget(self.vkeyboard)
#             self.layout.add_widget(self.list_view)
#             self.viewSwitchButton.text="Show Keyboard"
#             self.shown="list"
#         else:
#             self.layout.remove_widget(self.list_view)
#             self.viewSwitchButton.text="Show List"
#             self.shown="keyboard"

# class BuckshotApp(App): 
#         self.layout.remove_widget(self.list_view)
#         self.layout.add_widget(self.bottom)
#     def makeKeyboard(self):
#         keyboard=Window.request_keyboard(self._keyboard_close,self)
#         keyboard.widget.size_hint_y=0.5
#         if keyboard.widget:
#             self.vkeyboard=keyboard.widget
#             self.vkeyboard.layout='numeric.json'
#             # note, any entry that has non-'null' second element will not trigger on_key_down 
#         else:
#             self.vkeyboard=keyboard       
#         self.vkeyboard.bind(on_key_down=self.key_down)

#     def showKeyboard(self):
#         self.layout.remove_widget(self.vkeyboard)
#         self.layout.add_widget(self.vkeyboard)
#         self.shown="keyboard"
#     
#     def showList(self):
# #         self.vkeyboard.unbind(on_key_down=self.key_down)
# #         Window.release_all_keyboards()
# #         self.vkeyboard=None
# #         self.layout.remove_widget(self.bottom)
# #         self.layout.add_widget(self.list_view)
#         self.layout.remove_widget(self.list_view)
#         self.layout.add_widget(self.list_view)
#         self.shown="list"
        
    def selectionChanged(self,*args):
        if len(self.list_adapter.selection)>0:
            self.bestMatch=self.list_adapter.selection[0].text
        else:
            self.bestMatch=""
        Logger.info("Selection changed.  New best match:"+self.bestMatch)
  
    def key_down(self,keyboard,keycode,*args):
        Logger.info("key pressed: keyboard="+str(keyboard)+"  keycode="+str(keycode)+"  args:"+str(args))
        if isinstance(keycode,tuple):
            keycode=keycode[1]
        if keycode=="backspace":
            self.coordsEntered=self.coordsEntered[0:len(self.coordsEntered)-1]
        else:
            self.coordsEntered+=format(keycode)
        self.coordsField.text=self.coordsEntered
        self.coordsChanged()
        return True

    
    def _keyboard_close(self,*args):
        pass
       
    def build(self):
        # these statements could go in __init__:
        Logger.info('build called')
        # TO DO: better cross-platform / universal gpx Dir selection,
        #   and fallbacks if permission is denied
#         self.gpxFileName="C:\\Users\\caver\\Downloads\\buckshotApp.gpx"
        if platform in ('windows'):
            self.gpxDir=os.path.join(os.path.expanduser('~'),"Downloads")
        else:
            # from https://stackoverflow.com/a/40321516/3577105
            self.gpxDir=os.path.dirname(os.path.abspath(__file__))
        self.gpxFileName=os.path.join(self.gpxDir,"buckshotApp.gpx")
        self.coordDdStringList=[]
        self.coordDMmStringList=[]
        self.coordDMSsStringList=[]
        self.bestMatch=""
        
#         Window.softinput_mode='pan'
        self.coordsEntered=""
        self.shown="keyboard"
        
        data_items=[]
        
        self.layout=BoxLayout(orientation='vertical')
        self.coordsField=TextInput(hint_text='Coordinates',
                multiline=False,font_size='20pt',size_hint=(1,0.1),
                hint_text_color=(1,1,1,0.5))
        self.coordsField.bind(text=self.coordsChanged) # this seems to work best for now
#         self.coordsField.bind(on_key_down=self.key_down)
#         Window.bind(on_key_down=self.key_down)
        self.layout.add_widget(self.coordsField)
         
        buttonsLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
        self.viewSwitchButton=Button(text='View List\nD.d : 0\nDM.m : 0\nDMS.s : 0')
#         self.viewSwitchButton.bind(on_press=self.viewSwitch)
        buttonsLayout.add_widget(self.viewSwitchButton)
        goButton=Button(text='Create Markers')
        goButton.bind(on_press=self.createMarkers)
        buttonsLayout.add_widget(goButton)
        self.layout.add_widget(buttonsLayout)
        
        # 'bottom' is either a placeholder for the keyboard, or the list
#         self.bottom=Widget(size_hint_y=0.65)
#         self.layout.add_widget(self.bottom)
        
#         self.vkeyboard=None
    
        
#         keyboard=Window.request_keyboard(self._keyboard_close,self,'number')
#         keyboard.widget.size_hint_y=0.2
#         if keyboard.widget:
#             self.vkeyboard=keyboard.widget
#             self.vkeyboard.layout='numeric.json'
#         else:
#             self.vkeyboard=keyboard
#          
#         self.vkeyboard.bind(on_key_down=self.key_down)
         
#         self.list_item_args_converter = \
#                 lambda row_index, rec: {'text': rec['text'],
#                                         'is_selected': rec['is_selected'],
#                                         'size_hint_y': None,
#                                         'height': 25}

#         # Here we create a dict adapter with 1..100 integer strings as
#         # sorted_keys, and integers_dict from fixtures as data, passing our
#         # CompositeListItem kv template for the list item view. Then we
#         # create a list view using this adapter. args_converter above converts
#         # dict attributes to ctx attributes.
#         self.dict_adapter = DictAdapter(sorted_keys=[str(i) for i in range(100)],
#                                    data=integers_dict,
#                                    args_converter=self.list_item_args_converter,
#                                    template='CustomListItem')
#  
#         self.list_view = ListView(adapter=self.dict_adapter)
#  
#         self.layout.add_widget(self.list_view)
         
        
        # copied from list_reset_data.py: uses ListAdapter instead of DictAdapter
        list_item_args_converter = lambda row_index, obj: {'text': obj.name,
                                                           'size_hint_y': None,
                                                           'height': 65}
 
        self.list_adapter = \
                ListAdapter(data=data_items,
                            args_converter=list_item_args_converter,
                            selection_mode='single',
                            propagate_selection_to_data=False,
                            allow_empty_selection=True,
                            cls=ListItemButton)
 
        self.list_adapter.bind(on_selection_change=self.selectionChanged)
         
        self.list_view = ListView(adapter=self.list_adapter,size_hint_y=0.65)

        self.layout.add_widget(self.list_view)

        Logger.info('build2')
#         self.showKeyboard()
        Logger.info('build3')       
        return self.layout
    
        
if __name__ == '__main__':
    Logger.info('starting buckshotApp')
    BuckshotApp().run()
