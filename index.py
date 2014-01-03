#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, urllib2, re, time, os.path, cPickle, threading, Queue, sys, os, time, traceback
import httplib
import zipfile, gzip, StringIO
from BeautifulSoup import BeautifulSoup
from xml.dom.minidom import Document
from xml.dom.minidom import getDOMImplementation
import cgi
#import cgitb; cgitb.enable()  # for troubleshooting
import socket
timeout = 20
socket.setdefaulttimeout(timeout)
# debug: 1 - less verbose
#        2 - verbose
debug = 0
sent_debug_header = False

useragent = 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)'
useragent = 'toptvxmlgrabber/1.0 (compatible; MSIE 6.0; Windows NT 5.1)'
fn = 'xmltv_toptv_all.xml'


def debug_print(s):
    global sent_debug_header
    if not sent_debug_header:
        print 'Content-type: text/html; charset=utf-8\nCache-Control: no-cache\n'
        sent_debug_header = True
    print s


def get_html(channelid, day):
    if not os.path.exists('cache'):
        try:
            os.mkdir('cache')
        except OSError, e:
            debug_print(e)
    datestr = time.strftime('%Y-%m-%d', day)
    now = time.strftime('%Y_%m_%d')
    hfile = 'cache/' + '.'.join([datestr, str(channelid), '[%s]'%now, 'html'])
    if not os.path.exists(hfile):
        data = urllib.urlencode(
                {'filter_channel': channelid,
                 'filter_date': datestr,
                 'option': 'com_tvguide',
                 'view': 'tvguide'})
        url = 'http://www.ondigitalmedia.co.za/toptvwebsite/index.php'
        headers = {'User-agent': useragent}
        if debug == 2: print '%s: fetching from %s?%s' %(hfile, url, data)
        req = urllib2.Request(url, data, headers)
        try:
            rawhtml = urllib2.urlopen(req).read()
            if os.path.isdir('cache'):
                f = open(hfile, 'w')
                f.write(rawhtml)
                f.close()
        except urllib2.URLError, e:
            debug_print(e)
            if debug == 2:debug_print(hfile)
            rawhtml = ''
        except httplib.BadStatusLine, e:
            debug_print(e)
            if debug == 2:debug_print(hfile)
            rawhtml = ''
        except socket.timeout, e:
            debug_print(e)
            if debug == 2:debug_print(hfile)
            rawhtml = ''
        #except:
        #    debug_print('default exception - something happened while getting html but dunno what')
         #   debug_print(channelid)
          #  rawhtml = ''
    else:
        if debug == 2: print '%s: already got, not getting again'%hfile
        f = open(hfile, 'r')
        rawhtml = f.read()
        f.close()
    return rawhtml


def get_toptv(channelid=25, day=None):
    if not day:
        day = time.gmtime()
    datestr = time.strftime('%Y-%m-%d', day)
    yearstr = time.strftime('%Y', day)
    now = time.strftime('%Y_%m_%d')
    programs = []
    pfile = 'cache/' + '.'.join([datestr, str(channelid), '[%s]'%now, 'pkl'])
    if not os.path.exists(pfile):
        rawhtml = get_html(channelid, day)
        if rawhtml:
            soup = BeautifulSoup(rawhtml)
            try:
                guidecontent = soup.find('div', {'id': 'guidecontent'})
                cells = guidecontent.findAll('div', 'tooltip')
            except (IndexError, AttributeError), e:
                cells = []
                debug_print('No tables or rows found')
                debug_print(e)

            global channelnames
            pchannel = channelnames[channelid]
            plogo = 'http://www.ondigitalmedia.co.za/toptvwebsite/images/logos/%s.png' %pchannel.replace(' ', '_')
            for cell in cells:
                if cell.contents:
                    pdate = actors = ptitle = pstitle = prating = timestr = pdescription = pseason = pepisode = pepisodedesc = pepisodenr = ''
                    ptime = time.gmtime(0)
                    pactors = []
                    try:
                        timestr = cell.i.string.strip() #19 Jul 13:25 PM
                        ptime = time.strptime(yearstr + timestr, '%Y%d %b %H:%M %p')

                        if cell.find('span', 'h4'):
                            episodestr = cell.find('span', 'h4').string
                            r = re.search('(E\d+):\s*(.*)', episodestr)
                            if r:
                                pepisode = r.group(1).strip()
                                pepisodedesc = r.group(2).strip()

                        titlestr = cell.find('span', 'h3').string
                        r = re.search('(.*):\s*(S\d+).*', titlestr)
                        if r:
                            pseason = r.group(2).strip()
                            ptitle = '%s %s%s'.strip() %(r.group(1), pseason, pepisode)
                        else:
                            ptitle = titlestr.strip()

                        if pseason or pepisode:
                            s_nr = e_nr = ''
                            try:
                                if pseason: s_nr = str(int(pseason.strip('sS')) - 1)
                                if pepisode: e_nr = str(int(pepisode.strip('eE')) - 1)
                                pepisodenr = '%s.%s.' %(s_nr, e_nr)
                            except ValueError, e:
                                debug_print(e)
                                debug_print(pseason + pepisode + titlestr)

                        para = cell.findAll('p')[1]
                        if para.span:
                            prating = para.find('span', 'pg').text.strip()
                            pdescription = para.contents[1].string
                        else:
                            pdescription = para.text
                        pdescription = unicode(pdescription.replace('&ndash;', '').strip())
                    except AttributeError, e:
                        debug_print(e)
                        debug_print(cell)
                        pdescription = 'error'
                        pactors = []
                    except TypeError, e:
                        debug_print(e)
                    programs.append({
                        'start': ptime,
                        'title': ptitle,
                        'stitle': pstitle,
                        'desc': pdescription,
                        'channel': channelid,
                        'logo': plogo,
                        'channelname': pchannel,
                        'rating': prating,
                        'actors': pactors,
                        'date': pdate,
                        'episodenr': pepisodenr,
                        })
            FILE = open(pfile, 'wb')
            cPickle.dump(programs, FILE)
            if debug == 2: debug_print('%s: dumped pickle'%pfile)
            FILE.close()
    else:
        FILE = open(pfile, 'rb')
        try:
            programs = cPickle.load(FILE)
        except EOFError, e:
            debug_print('EOF in pkl file')
            if e: debug_print(e)
            os.remove(pfile)
            debug_print('removed '+pfile)
        except cPickle.BadPickleGet, e:
            debug_print('BadPickleGet Error in pkl file')
            if e: debug_print(e)
            os.remove(pfile)
            debug_print('removed '+pfile)
        except ValueError, e:
            debug_print('ValueError in pkl file')
            if e: debug_print(e)
            os.remove(pfile)
            debug_print('removed '+pfile)
        if debug == 2: debug_print('%s: got pickle'%pfile)
        FILE.close()
    return programs

def xml(programs):
    impl = getDOMImplementation()
    dt = impl.createDocumentType('tv', None, "http://xmltv.cvs.sourceforge.net/viewvc/xmltv/xmltv/xmltv.dtd")
    doc = impl.createDocument(None, 'tv', dt)
    tv = doc.documentElement
    tv.setAttribute('source-info-url', 'http://toptv.co.za')
    tv.setAttribute('generator-info-name', 'http://foo.co.za/')
    root = doc.firstChild
    doc.insertBefore(doc.createProcessingInstruction("xml-stylesheet", "type=\"text/xsl\" href=\"xmltv.xsl\""), root)
    #print doc.toprettyxml(encoding='utf-8')

    chanlist = {}
    for program in programs:
        if program['channel'] not in chanlist:
            chanlist[program['channel']] = [program['channelname'], program['logo']]
    for chan in chanlist.keys():
        channel = doc.createElement("channel")
        channel.setAttribute('id','%s.toptv.co.za'%chan)
        tv.appendChild(channel)
        displayname = doc.createElement("display-name")
        channel.appendChild(displayname)
        displaynametext = doc.createTextNode(chanlist[chan][0])
        displayname.appendChild(displaynametext)
        icon = doc.createElement("icon")
        channel.appendChild(icon)
        icon.setAttribute('src', chanlist[chan][1])

    for i in range(len(programs)):
        program = programs[i]
        try:
            nextprogram = programs[i+1]
            if nextprogram['channel'] != program['channel']:
                nextprogram = program
                if debug == 2: debug_print('last program of this channel')
                if debug == 2: debug_print(str(nextprogram))
        except IndexError:
            nextprogram = program
            if debug == 2: debug_print('no next program')
            if debug == 2: debug_print(str(nextprogram))
        programme = doc.createElement('programme')
        tv.appendChild(programme)
        programme.setAttribute('start', time.strftime('%Y%m%d%H%M%S +0200', program['start']))
        programme.setAttribute('stop', time.strftime('%Y%m%d%H%M%S +0200', nextprogram['start']))
        programme.setAttribute('channel', '%s.toptv.co.za'%program['channel'])

        title = doc.createElement('title')
        programme.appendChild(title)
        titletext = doc.createTextNode(program['title'])
        title.appendChild(titletext)

        #stitle = doc.createElement('stitle')
        #programme.appendChild(stitle)
        #try:
        #    stitletext = doc.createTextNode(program['stitle'])
        #except KeyError:
        #    stitletext = doc.createTextNode('')
        #stitle.appendChild(stitletext)

        desc = doc.createElement('desc')
        programme.appendChild(desc)
        descriptiontext = doc.createTextNode(program['desc'])
        desc.appendChild(descriptiontext)

        if 'stitle' in program and program['stitle']:
            stitle = doc.createElement('sub-title')
            programme.appendChild(stitle)
            stitletext = doc.createTextNode(program['stitle'])
            stitle.appendChild(stitletext)

        if 'rating' in program and program['rating']:
            rating = doc.createElement('rating')
            programme.appendChild(rating)
            rvalue = doc.createElement('value')
            rating.appendChild(rvalue)
            ratingtext = doc.createTextNode(program['rating'])
            rvalue.appendChild(ratingtext)

        if 'date' in program and program['date']:
            date = doc.createElement('date')
            programme.appendChild(date)
            datetext = doc.createTextNode(program['date'])
            date.appendChild(datetext)

        if 'actors' in program and program['actors']:
            credits = doc.createElement('credits')
            programme.appendChild(credits)
            for actor in program['actors']:
                pactor = doc.createElement('actor')
                credits.appendChild(pactor)
                actortext = doc.createTextNode(actor)
                pactor.appendChild(actortext)

        if 'episodenr' in program and program['episodenr']:
            episodenr = doc.createElement('episode-num')
            episodenr.setAttribute('system', 'xmltv_ns')
            programme.appendChild(episodenr)
            episodenrtext = doc.createTextNode(program['episodenr'])
            episodenr.appendChild(episodenrtext)

    return doc

Qin  = Queue.Queue()
allprograms = {}

def process_queue():
    while True:
        #try:
            c, t = Qin.get() #will wait here!
            if c is None:
                break
            tt = time.gmtime(time.time()+(60*60*24*t))
            programs = get_toptv(c, tt)
            allprograms[(c, t)] = programs
            Qin.task_done()
            #time.sleep(0.5) #just slows down and idle scripts get killed...?
            if debug == 2: print 'task done', c, tt[2], '|' , Qin.qsize()
        #except:
         #   Qin.task_done()



def getchan(channels=[], days=1):
    queue = Queue.Queue(maxsize=300)
    programs = []
    threads = []
    times = range(days)
    for i in range(1): # More threads can cause Hetzner to kill script
            thread = threading.Thread(target=process_queue)
            thread.daemon = True
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)

    for c in channels:
        for t in times:
            #c = int(c)
            #tt = time.gmtime(time.time()+(60*60*24*t))
            #programs += get_toptv(c, day=tt)

            Qin.put((c, t))
            if debug == 2: debug_print(' '.join(['task put', str(c), str(t), '|' , str(Qin.qsize())]))

    Qin.join()
    for t in threads:
        Qin.put((None, None))

    for c in channels:
        for t in times:
            #c = int(c)
            #tt = time.gmtime(time.time()+(60*60*24*t))
            try:
                programs += allprograms[(c, t)]
            except KeyError, e:
                debug_print('KeyError')
                debug_print(e)
    return programs

def doc2xml(doc):
        text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
        prettyXml = text_re.sub('>\g<1></', doc.toprettyxml(encoding='utf-8'))
        text_re = re.compile('>\n\s+\n\s+</', re.DOTALL)
        prettyXml = text_re.sub('></', prettyXml)
        return prettyXml


def cleanup():
    # remove old files first
    if debug >= 1: debug_print('cleaning up')
    from operator import itemgetter, attrgetter
    import glob
    def custom_rm(filename = None):
        if filename:
            os.remove(filename)
            time.sleep(0.1)


    filesindir = glob.glob('cache/*.html')
    for fname in filesindir:
        #print os.stat(fname).st_mtime , (time.time() - 60*60*24)
        if os.stat(fname).st_mtime < (time.time() - 60*60*24):
            if debug >= 1: debug_print('removing %s' %fname)
            custom_rm(fname)

    filesindir = glob.glob('cache/*.pkl')
    for fname in filesindir:
        #print os.stat(fname).st_mtime , (time.time() - 60*60*24)
        if os.stat(fname).st_mtime < (time.time() - 60*60*24):
            if debug >= 1: debug_print('removing %s' %fname)
            custom_rm(fname)



def getall(few=0):
    # get new ones
    if debug >= 1: debug_print('getting all')
    #channels = range(1, 54+1)
    #channels.append(59)
    #channels.append(68)
    #channels += range(71, 75+1)
    #channels = channelnames
    channels = range(1, 60+1)
    days = 1

    try:
        FILE = open('last_update', 'rb')
        last_update = cPickle.load(FILE)
        FILE.close()
    except (IOError, EOFError, cPickle.UnpicklingError, TypeError), e:
        last_update = time.localtime(0)
    if time.mktime(last_update) > (time.time() - 1*24*60*60) or few:
        if debug >= 1: debug_print('not getting all - too soon')

        # only do a few
        inc = int(len(channels)/12)
        if debug >= 1: debug_print('increment: %d' %inc)
        idx = 0
        try:
            FILE = open('cache/idx', 'rb')
            idx = int(FILE.read())
            if idx >= len(channels): idx = 0
            FILE.close()
        except IOError, e:
            debug_print('File error when checking idx (no file?)')
            debug_print(e)


        do_channels = channels[idx:idx+inc]
        if debug >= 1: debug_print('getting channels ' + str(do_channels))
        getchan(do_channels, days)
        if debug >= 1: debug_print('got channels')

        try:
            FILE = open('cache/idx', 'wb')
            if idx < len(channels):
                FILE.write(str(idx+inc))
            else:
                FILE.write(str(0))
            FILE.close()
        except IOError, e:
            debug_print('File error when writing idx')
            debug_print(e)

        sys.exit(0)


    programs = getchan(channels, days)
    if debug >= 1: debug_print('generating xml')
    doc = xml(programs)
    prettyXml = doc2xml(doc)
    try:
        if os.path.exists(fn):
            os.remove(fn)
        f = open(fn, 'wb')
        f.write(prettyXml)
        f.close
        if debug >= 1: debug_print('written %s'%fn)

        if os.path.exists('%s.gz'%fn):
            os.remove('%s.gz'%fn)
        zz = gzip.open('%s.gz'%fn, 'wb', compresslevel=6)
        zz.write(prettyXml)
        zz.close()
        if debug >= 1: debug_print('written %s.gz'%fn)

        if os.path.exists('%s.zip'%fn):
            os.remove('%s.zip'%fn)
        zz = zipfile.ZipFile('%s.zip'%fn, 'w', compression=zipfile.ZIP_DEFLATED)
        zz.debug = 3
        zi = zipfile.ZipInfo(fn)
        zi.external_attr = 0777 << 16L
        zz.writestr(zi, prettyXml)
        zz.close()
        if debug >= 1: debug_print('written %s.zip'%fn)

        try:
            FILE = open('last_update', 'wb')
            cPickle.dump(time.localtime(), FILE)
            FILE.close()
        except IOError, e:
            debug_print(e)
        if debug >= 1: debug_print('generated xml')
    except IOError, e:
        debug_print(e)


def getxmlchan(channels=[], days=1):
    programs = getchan(channels, days)
    if programs:
        doc = xml(programs)
        prettyXml = doc2xml(doc)
    else:
        prettyXml = ''
    return prettyXml


def log_user(ip, ua, q, via, xf, ref, poststr, ltime):
    pfile = 'log.pkl'

    try:
        FILE = open(pfile, 'rb')
        log = cPickle.load(FILE)
        FILE.close()
    except IOError, e:
        debug_print(e)
        log = {}

    pfilebak = pfile + time.strftime('.%Y%m%d') + '.bak'
    FILE = open(pfilebak, 'wb')
    cPickle.dump(log, FILE)
    FILE.close()

    log[ltime] = (ip, ua, q, via, xf, ref, poststr)

    FILE = open(pfile, 'wb')
    cPickle.dump(log, FILE)
    FILE.close()

def pretty_date(ttime=False, html5=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime
    now = datetime.now()
    if type(ttime) is int or type(ttime) is float:
        diff = now - datetime.fromtimestamp(ttime)
    elif isinstance(ttime, datetime):
        diff = now - ttime
    elif isinstance(ttime, time.struct_time):
        diff = now - datetime.fromtimestamp(time.mktime(ttime))
    elif not ttime:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        rval = ''

    elif day_diff == 0:
        if second_diff < 10:
            rval = " a few seconds ago"
        elif second_diff < 60:
            rval = str(second_diff) + " seconds ago"
        elif second_diff < 120:
            rval =  "a minute ago"
        elif second_diff < 3600:
            rval = str( second_diff / 60 ) + " minutes ago"
        elif second_diff < 7200:
            rval = "an hour ago"
        elif second_diff < 86400:
            rval = str( second_diff / 3600 ) + " hours ago"
    elif day_diff == 1:
        rval = "Yesterday"
    elif day_diff < 7:
        rval = str(day_diff) + " days ago"
    elif day_diff < 31:
        rval = str(day_diff/7) + " weeks ago"
    elif day_diff < 365:
        rval = str(day_diff/30) + " months ago"
    else:
        rval = str(day_diff/365) + " years ago"

    if html5:
        datetime = time.strftime('%Y-%m-%dT%H:%MZ', ttime)
        return '<time datetime="%s">%s</time>' %(datetime, rval)
    else:
        return rval


options = '''
<option value="01">Al Jazeera</option>
<option value="02">BBC World</option>
<option value="03">Current TV</option>
<option value="04">e.tv</option>
<option value="05">Eurosport</option>
<option value="06">Fashion</option>
<option value="07">Fine Living Network</option>
<option value="08">Fox News</option>
<option value="09">France 24</option>
<option value="10">GOD TV</option>
<option value="11">Hi Nolly</option>
<option value="12">Inspiration Network</option>
<option value="13">BabyTV</option>
<option value="14">Classica</option>
<option value="15">C Music TV</option>
<option value="16">Fuel TV</option>
<option value="17">JimJam</option>
<option value="18">Kerrang!</option>
<option value="19">Kids Co.</option>
<option value="20">Metro Goldwyn Mayer</option>
<option value="21">Music Choice</option>
<option value="22">Top Learn</option>
<option value="23">MSNBC</option>
<option value="24">RTP International</option>
<option value="25">SABC 1</option>
<option value="26">SABC 2</option>
<option value="27">SABC 3</option>
<option value="28">Setanta Africa</option>
<option value="29">Top Gospel</option>
<option value="30">Top One</option>
<option value="31">Zee Cinema</option>
<option value="32">Kiss</option>
<option value="33">Magic TV</option>
<option value="34">One Music</option>
<option value="35">Q TV</option>
<option value="36">Smash Hits</option>
<option value="37">Top Junior</option>
<option value="38">Black Entertainment Television</option>
<option value="39">Discovery I.D. </option>
<option value="40">Discovery Science</option>
<option value="41">Discovery Travel &amp; Living</option>
<option value="42">Fox Entertainment</option>
<option value="43">Fox Retro</option>
<option value="44">Natura</option>
<option value="45">Star!</option>
<option value="46">Top Crime</option>
<option value="47">Top Explore</option>
<option value="48">Top History</option>
<option value="49">Fox FX</option>
<option value="50">Showtime</option>
<option value="51">Silver</option>
<option value="52">Top Movies</option>
<option value="53">Top Movies +2</option>
<option value="54">Top Movies +24</option>
<option value="59">ASTV</option>
<option value="68">Star Plus</option>
<option value="71">Star Gold</option>
<option value="72">Star Vijay</option>
<option value="73">Channel V</option>
<option value="74">MUTV</option>
<option value="75">Al Mizan</option>
'''

options = '''
<option value="Al Jazeera International">Al Jazeera International</option>
<option value="Al Mizan">Al Mizan</option>
<option value="ASTV Afrikaans Satellite">ASTV Afrikaans Satellite</option>
<option value="Baby TV">Baby TV</option>
<option value="BBC World News">BBC World News</option>
<option value="Bet">Bet</option>
<option value="C MUSIC TV">C MUSIC TV</option>
<option value="CANAL NATURA">CANAL NATURA</option>
<option value="CLASSICA">CLASSICA</option>
<option value="Current TV">Current TV</option>
<option value="Discovery Europe Science">Discovery Europe Science</option>
<option value="Discovery Travel &amp; Living Euro">Discovery Travel &amp; Living Euro</option>
<option value="E TV">E TV</option>
<option value="Eurosport News">Eurosport News</option>
<option value="Fashion TV">Fashion TV</option>
<option value="Fine Living Net ">Fine Living Net </option>
<option value="Fox Entertainment">Fox Entertainment</option>
<option value="Fox FX">Fox FX</option>
<option value="Fox News Channel">Fox News Channel</option>
<option value="Fox Retro">Fox Retro</option>
<option value="France 24">France 24</option>
<option value="FUEL TV">FUEL TV</option>
<option value="God Channel">God Channel</option>
<option value="HI NOLLY">HI NOLLY</option>
<option value="INSPIRATION NETWORK INTERNTL">INSPIRATION NETWORK INTERNTL</option>
<option value="Investigation Discovery Europe">Investigation Discovery Europe</option>
<option value="JimJam">JimJam</option>
<option value="Kerrang!">Kerrang!</option>
<option value="Kidsco">Kidsco</option>
<option value="Kiss">Kiss</option>
<option value="Magic">Magic</option>
<option value="MGM">MGM</option>
<option value="MSNBC">MSNBC</option>
<option value="MUTV">MUTV</option>
<option value="One Music">One Music</option>
<option value="QFHM Music TV">QFHM Music TV</option>
<option value="RTP Internacional">RTP Internacional</option>
<option value="SABC 1">SABC 1</option>
<option value="SABC 2">SABC 2</option>
<option value="SABC 3">SABC 3</option>
<option value="Setanta Africa">Setanta Africa</option>
<option value="Showtime">Showtime</option>
<option value="Silver">Silver</option>
<option value="Smash Hits!">Smash Hits!</option>
<option value="Star">Star</option>
<option value="Star Channel V">Star Channel V</option>
<option value="Star Gold">Star Gold</option>
<option value="Star Plus">Star Plus</option>
<option value="Star Vijay">Star Vijay</option>
<option value="Top Crime">Top Crime</option>
<option value="Top Explore">Top Explore</option>
<option value="Top Gospel">Top Gospel</option>
<option value="Top History">Top History</option>
<option value="Top Junior">Top Junior</option>
<option value="Top Learn">Top Learn</option>
<option value="Top Movie">Top Movie</option>
<option value="Top Movies Plus 2 ">Top Movies Plus 2 </option>
<option value="Top Movies Plus 24    ">Top Movies Plus 24    </option>
<option value="Top One">Top One</option>
<option value="Zee Cinema UK">Zee Cinema UK</option></select>
'''

options = '''
<option value="58" selected="selected">Top One</option>
<option value="49">Top Crime</option>
<option value="50">Top Explore</option>
<option value="51">Top Gospel</option>
<option value="52">Top History</option>
<option value="53">Top Junior</option>
<option value="54">Top Learn</option>
<option value="55">Top Movies +2</option>
<option value="56">Top Movies +24</option>
<option value="57">Top Movies</option>
<option value="2">Al Jazeera International</option>
<option value="3">Al Mizan</option>
<option value="4">ASTV</option>
<option value="5">Baby TV</option>
<option value="6">BBC World News</option>
<option value="7">BET</option>
<option value="8">C MUSIC TV</option>
<option value="9">Channel [V]</option>
<option value="10">Classica</option>
<option value="11">Current TV</option>
<option value="12">Discovery Science</option>
<option value="13">Discovery Travel &amp; Living</option>
<option value="14">E TV</option>
<option value="15">Eurosport News</option>
<option value="16">Fashion TV</option>
<option value="17">Fine Living Network</option>
<option value="1">Fox Entertainment</option>
<option value="18">Fox News Channel</option>
<option value="19">Fox Retro</option>
<option value="20">France 24</option>
<option value="21">FUEL TV</option>
<option value="22">FX</option>
<option value="23">God TV</option>
<option value="24">Hi Nolly</option>
<option value="25">ID Investigation Discovery</option>
<option value="26">Inspiration</option>
<option value="27">JimJam</option>
<option value="28">Kerrang!</option>
<option value="29">Kidsco</option>
<option value="30">Kiss</option>
<option value="31">Magic</option>
<option value="32">MGM</option>
<option value="33">MSNBC</option>
<option value="34">MUTV</option>
<option value="35">Natura</option>
<option value="36">One Music</option>
<option value="37">Q</option>
<option value="38">RTP International</option>
<option value="39">SABC 1</option>
<option value="40">SABC 2</option>
<option value="41">SABC 3</option>
<option value="42">Setanta Africa</option>
<option value="43">Showtime</option>
<option value="44">Silver</option>
<option value="45">Smash Hits!</option>
<option value="46">Star Gold</option>
<option value="47">Star Plus</option>
<option value="48">Star!</option>
<option value="59">Vijay</option>
<option value="60">Zee Cinema</option>
'''

channelnames = {
    1: 'Fox Entertainment',
    2: 'Al Jazeera International',
    3: 'Al Mizan',
    4: 'ASTV',
    5: 'Baby TV',
    6: 'BBC World News',
    7: 'BET',
    8: 'C MUSIC TV',
    9: 'Channel [V]',
    10: 'Classica',
    11: 'Current TV',
    12: 'Discovery Science',
    13: 'Discovery Travel &amp; Living',
    14: 'E TV',
    15: 'Eurosport News',
    16: 'Fashion TV',
    17: 'Fine Living Network',
    18: 'Fox News Channel',
    19: 'Fox Retro',
    20: 'France 24',
    21: 'FUEL TV',
    22: 'FX',
    23: 'God TV',
    24: 'Hi Nolly',
    25: 'ID Investigation Discovery',
    26: 'Inspiration',
    27: 'JimJam',
    28: 'Kerrang!',
    29: 'Kidsco',
    30: 'Kiss',
    31: 'Magic',
    32: 'MGM',
    33: 'MSNBC',
    34: 'MUTV',
    35: 'Natura',
    36: 'One Music',
    37: 'Q',
    38: 'RTP International',
    39: 'SABC 1',
    40: 'SABC 2',
    41: 'SABC 3',
    42: 'Setanta Africa',
    43: 'Showtime',
    44: 'Silver',
    45: 'Smash Hits!',
    46: 'Star Gold',
    47: 'Star Plus',
    48: 'Star!',
    49: 'Top Crime',
    50: 'Top Explore',
    51: 'Top Gospel',
    52: 'Top History',
    53: 'Top Junior',
    54: 'Top Learn',
    55: 'Top Movies Plus 2',
    56: 'Top Movies Plus 24',
    57: 'Top Movies',
    58: 'Top One',
    59: 'Vijay',
    60: 'Zee Cinema'
}

channels = []
if len(sys.argv) > 1:
    if sys.argv[1] == 'getall':
        getall()
        sys.exit(0)
    elif sys.argv[1] == 'few':
        getall(few=1)
        sys.exit(0)
    elif sys.argv[1] == 'cleanup':
        cleanup()
        sys.exit(0)
    elif sys.argv[1] == '1':
        channels = [1]
    elif sys.argv[1] == 'debug':
        debug = 1
        getall()
        sys.exit(0)
    elif sys.argv[1] == 'debugdebug':
        debug = 2
        getall(few=1)
        sys.exit(0)

form = cgi.FieldStorage()

ip = os.getenv('REMOTE_ADDR')
ua = os.getenv('HTTP_USER_AGENT')
q  = os.getenv('QUERY_STRING')
via  = os.getenv('HTTP_VIA')
xf  = os.getenv('HTTP_X_FORWARDED_FOR')
ref  = os.getenv('HTTP_REFERER')

posts = []
for key in form.keys():
    if isinstance(form[key], list):
        vs = []
        for v in form[key]:
            vs.append(v.value)
        vv = '['+','.join(vs)+']'
    else:
        vv = form[key].value
    posts.append(key+'='+vv)
poststr = '&'.join(posts)

log_user(ip, ua, q, via, xf, ref, poststr, time.time())

try:
    FILE = open('last_update', 'rb')
    last_update = cPickle.load(FILE)
    FILE.close()
except (IOError, EOFError, cPickle.UnpicklingError, TypeError), e:
    last_update = time.localtime(0)

if not channels:
    channels = form.getlist('channel')
days = int(form.getfirst('days', 1))
compress = int(form.getfirst('compress', 0))
if days > 3:
    compress = 1

if debug == 2: debug_print(channels)

## For debugging:
#compress = 0
#channels = [58]
#channels = range(1, 55)
days = 1

if channels:
    xmlstring = getxmlchan(channels, days)
    if not sent_debug_header:
        if xmlstring:
            if not compress:
                print 'Content-type: text/xml; charset=utf-8\nCache-Control: no-cache\n'
                print xmlstring
            else:
                io = StringIO.StringIO()
                z = gzip.GzipFile(fileobj=io, mode='wb', compresslevel=6).write(xmlstring)
                compressed = io.getvalue()
                io.close()

                print 'Content-type: application/gzip'
                print 'Content-Disposition: attachment; filename="xmltv_%d.xml.gz"'%days
                print 'Content-length: %d\n' %len(compressed)
                sys.stdout.write(compressed)

        else:
            print 'Content-type: text/html; charset=utf-8\nCache-Control: no-cache\n'
            print '<!DOCTYPE html><html><head><title>Top TV xmltv</title></head><body><p>Nothing to show.</p></body></html>'

    else:
        print '<br />Oops, something happened. No xml for you ;) Please try again...'

else:
    scriptname = os.path.basename(sys.argv[0]).replace('./', '')
    print 'Content-type: text/html; charset=utf-8\nCache-Control: no-cache\n'
    content = '''<!DOCTYPE html><html><head><title>Top TV xmltv</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <link type="text/css" rel="stylesheet" href="css/style.min.css" />
    <!--[if IE 6]>
    <style type="text/css">
        #wrapper {
            height: 100%%;
        }
    </style>
    <![endif]-->
    <script type="text/javascript">
        (function(w,d) {
            var js = function(a,b){
                var c='script',s=d.createElement(c),t=d.getElementsByTagName(c)[0];s.async=true;
                if(b){
                    if(s.readyState){
                        s.onreadystatechange=function(){
                            if(s.readyState==='loaded'||s.readyState==='complete'){
                                s.onreadystatechange=null;
                                b();
                            }
                        }
                    }
                    else{
                        s.onload=function(){
                            b();
                        }
                    }
                }
                s.src=a;t.parentNode.insertBefore(s,t)
            };
            js('http://ajax.googleapis.com/ajax/libs/jquery/1.6.1/jquery.min.js',
                function(){
                    $.getScript('js/jquery.url_plus_validate_plus_page.min.js', function() {
                      $('#title h1').css("color","#333");
                    });
                }
            );
        })(window, document);
    </script>
    </head>
    <body>
        <div id="wrapper">
            <header id="header">
                <div id="title">
                    <h1>Top TV xmltv</h1>
                    <h2>ver. 0.6 alpha</h2>
                    <h3>Shaping up</h3>
                </div>
            </header>
            <div id="content">
                <section id="left">
                    <section class="notice alert">
                        <h3><time datetime="2013-01-15">15 January 2013</time></h3>
                        <p>Changed Top TV guide url.</p>
                    </section>
                    <section class="notice alert">
                        <h3><time datetime="2012-01-23">23 January 2012</time></h3>
                        <p>Top TV guide format changed - fixed descriptions and added series numbers. Please report any bugs.</p>
                    </section>
                    <section class="notice alert">
                        <h3><time datetime="2011-07-05">5 July 2011</time></h3>
                        <p>Should be ok now with basic features. Days limited to one week. Still, expect bugs...</p>
                    </section>
                    <section class="notice alert">
                        <h3><time datetime="2011-05-23">23 May 2011</time></h3>
                        <p>Top TV changed their tv schedule pages again which will require a few changes. Expect bugs...</p>
                    </section>
                    <p>Select some channels to download from the list on the right. You can also choose to display programs in your browser by unchecking the <em>compress and download</em> option.</p>
                    <div class="notice">
                        <p>Download all channels for the next 14 days in
                        <a rel="nofollow" href="%s.gz">.gz</a>
                        <a rel="nofollow" href="%s.zip">.zip</a> or
                        <a rel="nofollow" href="%s">uncompressed</a> format.
                        <br /><em>(Please choose one of the compressed formats to minimize data transfer)</em></p>
                    </div>
                    <p>Please also check out the official <a rel="nofollow" href="http://www.ondigitalmedia.co.za/toptvwebsite/index.php?option=com_tvguide" onclick="_gaq.push(['_trackEvent', 'External click', 'external', 'toptv.co.za']);">Top TV guide</a>.</p>
                    <p><a href="http://blog.floatinginspace.za.org/2010/internet/top-tv-schedule-in-xmltv-format/134/" onclick="_gaq.push(['_trackEvent', 'External click', 'external', 'blog.floatinginspace.za.org']);">Comments or error reports
                        here please.</a></p>
                    <p><del>For DSTV xmltv check out http://zaxmltv.flash.za.org/</del></p>
                </section>
                <aside id="right">
                    <form method="post" action="%s" id="formdownload" title="Channel download">
                     <p>
                         <select name="channel" title="channel" multiple="multiple" size="8" >
                            %s
                         </select>
                         <br />
                         <select disabled="disabled" name="days" title="days" >
                            <option selected="selected" value="1">1 day</option>
                            <option value="2">2 days</option>
                            <option value="3">3 days</option>
                            <option value="7">7 days (download only)</option>
                            <option value="14">14 days (download only)</option>
                         </select>
                         <br />
                         <label>Compress and download?</label>
                         <input type="checkbox" name="compress" value="1" checked="checked"/>
                         <br />
                         <input type="submit" value="submit" id="submit"/>
                     </p>
                    </form>
                </aside>
            </div>
            <footer id="footer">
                <div id="footmsg">
                    <span id="last_update">Last update was %s</span>
                </div>
            </footer>
        </div>
    </body></html>'''%(fn, fn, fn, scriptname, options, pretty_date(last_update, 1))
    remove_ws = re.compile(r"\s{2,}").sub
    content = remove_ws('\n', content)
    print content

if debug == 2: print threading.enumerate()
