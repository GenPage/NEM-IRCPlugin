from util import hook, http, web
import json, redis, time, tweepy, re, urllib2, socket

base_url = "http://bot.notenoughmods.com/"
r = redis.StrictRedis(host='localhost', port=6379, db=1)
cooldown = 2

def get_api(bot):
    consumer_key = bot.config.get("api_keys", {}).get("twitter_consumer_key")
    consumer_secret = bot.config.get("api_keys", {}).get("twitter_consumer_secret")

    oauth_token = bot.config.get("api_keys", {}).get("twitter_access_token")
    oauth_secret = bot.config.get("api_keys", {}).get("twitter_access_secret")

    if not consumer_key:
        return False

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(oauth_token, oauth_secret)

    return tweepy.API(auth)

def loadinterface(lists=None):

    response = urllib2.urlopen('http://bot.notenoughmods.com/?json')
    data = json.load(response)

    for list in data:
        lists.append(list)

def loadmods(modlist=None, mclist=None):

    total("clear")

    for mcv in mclist:
        loadlist(modlist, mcv)

def printlists(lists=None):

    result = ""
    for list in lists:
        if list == lists[-1]:
            result = result + "\x0303" + str(list) + "\x0f"
        else:
            result = result + "\x0303" + str(list) + "\x0f, "

    return result

def printmultimod(modlist=None, mcv=None, modname=None, multi=False, reply=None, message=None, nick=None):

    if not multi:
        result = printmod(modlist, mcv, modname, multi, reply)
        if len(result) < 20:
            if len(result) > 5:
                message(str(len(result)) + " mod(s) found. Replying privately...")
                for line in result:
                    time.sleep(2) 
                    message(line, target=nick)
            else:
                message(str(len(result)) + " mod(s) found.")
                for line in result:
                    time.sleep(2)
                    message(line)
        else:
            reply("Too many mods matched (" + str(len(result)) + ") Please refine your search.") 
    else:
        found = False
        results = []
        for version in mcv:
            result = printmod(modlist, version, modname, multi, reply)
            if result:
                found = True
                results.append(result)
        
	if found:
            if len(results) < 20:
                if len(results) > 5:
                    message(str(len(results)) + " mod(s) found. Replying privately..")
                    for line in results:
                        time.sleep(2)
                        message(line, target=nick)
                else:
                    message(str(len(results)) + " mod(s) found.")
                    for line in results:
                        time.sleep(2)
                        message(line)
            else:
                reply("Too many mods matched (" + str(len(results)) + ") Please refine your search")
        else:
            reply("Mod not found")

def printmod(modlist=None, mcv=None, modname=None, multi=False, reply=None):

    currentmodlist = modlist[mcv]
    modname = modname.lower()
    if multi:
        for name, info in currentmodlist.iteritems():
            if modname == name.lower():
                pmod = "[\x0312%s\x03] \x0306%s\x03 @ \x0303%s\x03 %s %s"
                if info['comment'] != "":
                    return pmod % (mcv, info['name'], info['version'], info['shorturl'], "(" + info['comment'] + ")")
                else:
                    return pmod % (mcv, info['name'], info['version'], info['shorturl'], "")
    else:
        format = "[\x0312%s\x03] \x0306%s\x03 @ \x0303%s\x03 %s %s"
        results = []
        for name, info in currentmodlist.iteritems():
            if modname in name.lower():
                if info['comment'] != "":
                    results.append(format % (mcv, info['name'], info['version'], info['shorturl'], "(" + info['comment'] + ")"))
                else:
                    results.append(format % (mcv, info['name'], info['version'], info['shorturl'], ""))
        if not results:
            return ['Mod not found.']    
        else:
            return results	

def loadlist(mods=None, list=None):

    response = urllib2.urlopen('http://bot.notenoughmods.com/' + str(list) + '.json')
    cleanresp = response.read()
    try:
        data = json.loads(cleanresp.replace('\r\n', ''))
    except:
        print(list)
        raise

    tempmodlist = {}
    for mod in data:            
        tempmodlist[mod['name']] = mod
    
    mods[list] = tempmodlist
    total("set", len(tempmodlist))

def help(command):

    if command == "total":
        return "nem total [list] - returns the total number of mods"
    elif command == "modinfo":
        return "nem modinfo <mod> [list] - returns a search result or exact multilisting"
    elif command == "lists":
        return "nem lists - returns all MC versions tracked by NEM"
    elif command == "missmodid":
        return "nem missmodid <list> - returns mods without a modid set"
    elif command == "blinks":
        return "nem blinks <list> - checks each mod link for non-OK http error code (200)"
    else:
        return "No help found - nonexistant command"

def total(method=None, incr=None):

    if method is "get":
        if r.exists('total'):
            return r.get('total')
        else:
            return "Total mods not tracked"
    elif method is "set":
        if r.exists('total'):
            r.incrby('total', incr)
        else:
            r.incr('total')
    elif method is "clear":
        if r.exists('total'):
            r.delete('total')
        else:
            return
    else:
        return "Error: Invalid method"

def modidcnt(mods=None, list=None, message=None, nick=None):

    count = 0
    missmods = []
    currentlist = mods[list]
    for name, info in currentlist.iteritems():
        if info['modid'] == "":
            count = count + 1
            missmods.append(str(name))
    
    if len(missmods) > 5:
        message(str(len(missmods)) + " missing modids found. Replying privately...")
        for mod in missmods:
            time.sleep(2)
            message("[\x0312" + str(list) + "\x03] " + str(mod), target=nick)
    elif len(missmods) > 0 and len(missmods) <= 5:
        for mod in missmods:
            time.sleep(2)
            message("[\x0312" + str(list) + "\x03] " + str(mod))
    
    return

@hook.singlethread
def brokenlinks(mods=None, list=None, message=None, nick=None):

    counts = {}
    extra = ""
    index = 0
    badmods = []
    currentlist = mods[list]
    for name, info in currentlist.iteritems():

        if index == 50 or index == 100 or index == 150 or index == 200 or index == 250 or index == 300 or index == 350 or index == 400 or index == 450:
            message("[\x0312" + str(list) + "\x03] " + str(index) + " mods processed for broken links")       
 
        if info['longurl'] != "":
            opener = urllib2.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.143 Safari/537.36'),('Accept', 'text/html')]
            try:
                resp = opener.open(info['longurl'])
            except urllib2.HTTPError, e:
                if e.code in counts:
                    counts[e.code] += 1
                else:
                    counts[e.code] = 1
                badmod = {'name': str(name), 'reason': e.code}
                badmods.append(badmod)
            except urllib2.URLError, e:
                if e.reason in counts:
                    counts[e.reason] += 1     
                else:
                    counts[e.reason] = 1
                badmod = {'name': str(name), 'reason': e.reason}
                badmods.append(badmod)
            except socket.timeout, e:
                if 'timeout' in counts:
                    counts['timeout'] += 1
                else:
                    counts['timeout'] = 1
                badmod = {'name': str(name), 'reason': "timeout"}
                badmods.append(badmod)
            else: 
                code = resp.getcode()
                if code in counts:
                    counts[code] += 1
                else:
                    counts[code] = 1
        index += 1
    
    if len(badmods) > 5:
        message(str(len(badmods)) + " broken links found. Replying privately...")        
        for mod in badmods:
            time.sleep(2)
            message("[\x0312" + str(list) + "\x03] " + str(mod), target=nick)
    elif len(badmods) > 0 and len(badmods) <= 5:
        for mod in badmods:
            time.sleep(2)
            message("[\x0312" + str(list) + "\x03] " + str(mod))

    time.sleep(2)
    message("[" + str(list) + "] Broken Link Checker complete. " + str(index) + " mods processed. ")
    time.sleep(2)
    message("Final results (HTTP codes): " + str(counts))
    return

@hook.command('nemlimit', permissions=["adminonly"])
def nemlimit(inp, bot=None, message=None):

    api = get_api(bot)

    message(str(api.rate_limit_status()), target="GenPage")

@hook.command(autohelp=True)
def nem(inp, reply=None, message=None, nick=None):
    """ nem <command> Available commands are: total, modinfo, lists, missmodid, blinks, about, help """

    mods = {}
    mclist = []
    loadinterface(mclist)
    loadmods(mods, mclist)
    args = inp.split()
    if len(args) < 1:
        return "Error: Please state a command"
    if args[0] == "lists":
        message(printlists(mclist))
    elif args[0] == "modinfo":
        if len(args) > 2:
            if args[2] in mods:
                printmultimod(mods, args[2], args[1], False, reply, message, nick)
            else:
                return "Error: MC List does not exist"
        elif len(args) < 2:
            return "Error: Please specify a mod. ~nem modinfo <modname> [list]"
        else:
            printmultimod(mods, mclist, args[1], True, reply, message, nick)
    elif args[0] == "total":
        if len(args) == 1:
            message("\x0306" + total("get") + "\x03 mods")
        if len(args) == 2:
            if args[1] in mods:
                message("\x0306" + str(len(mods[args[1]])) + "\x03 mods")
            else:
                return "Error: MC List does not exist"
    elif args[0] == "missmodid":
        if len(args) == 2:
            if args[1] in mods:
                modidcnt(mods, args[1], message, nick)
            else:
                return "Error: MC List does not exist"
        else:
            return "Error: Please state a list. ~nem modid <list>"
    elif args[0] == "blinks":
        blinksrunning = None
        if r.exists('blinksrunning'):
            blinksrunning = bool(r.get('blinksrunning'))
        if len(args) == 2:
            if args[1] in mods:
                if blinksrunning == True:
                    message("Broken link checker is already running")
                else:
                    r.set('blinksrunning', "1")
                    message("WARNING: This command takes a very long time to process")
                    brokenlinks(mods, args[1], message, nick)
                    r.set('blinksrunning', "")
            else:
                return "Error: MC List does not exist"
        else:
            return "Error: Please state a list. ~nem blinks <list>"
    elif args[0] == "site":
        if len(args) == 1:
            message("http://notenoughmods.com")
        else:
            return "Error: Invalid command"
    elif args[0] == "help":
        if len(args) == 1:
            message("For commands send an empty command '~nem'")
            time.sleep(2)
            message("Or provide a command '~nem help <command>'")
        elif len(args) == 2:
            message(help(args[1]))
        else:
            return "Error: Invalid command"        
    elif args[0] == "about":
        message("This is a NEM Plugin created by GenPage to help assist NEM contributors and users with vital functions")
    else:
        return "Error: command not found"

@hook.command('nemclearblink', permissions=["adminonly"])
def nemclearblink(inp, message=None):

    result = r.set('blinksrunning', "")
    if result:
        message("Completed")
    else: 
	message("Errored")

@hook.command('nemdebugchan', permissions=["adminonly"])
def nemdebug(inp, input=None, message=None, nick=None):

    args = inp.split()
    channel = str(input['chan'])
    nick = str(input['nick'])

    if args[0] == "channel":
        message("Chan: " + channel, target=nick)
        return
    if args[0] == "nick":
        message("Nick: " + nick, target=nick)
        return

@hook.regex(r'\[\00312(?P<list>.+?)\003\] \00306(?P<mod>.+?)\003 (?:added at|updated to) \00303(?P<version>.+?)\003')
@hook.singlethread
def nemlisten(match, input=None, bot=None, message=None):

    strip_re = r'(\003[0-9]{1,2}(?:,[0-9]{1,2})?)'

    mods = {}
    mclist = []
    loadinterface(mclist)
    loadmods(mods, mclist)

    channel = str(input['chan'])
    nick = str(input['nick'])
    
    if channel != "#notenoughmods":
        message("Bad Chan: " + channel, target="GenPage")
        return

    if nick != "ModBot":
        message("Bad Nick: " + nick, target="GenPage")
        return

    stripped_msg = re.sub(strip_re, '', match.group())
    stripped_msg = stripped_msg.replace('\003', '')

    api = get_api(bot)
    
    if api is None:
        message("Error retriveing api", target="GenPage")

    url = (str(mods[match.group(1)][match.group(2)]['shorturl']))
    modid = (str(mods[match.group(1)][match.group(2)]['modid']))

    if modid != "":
        status = stripped_msg + " " + url + " #" + modid
    else:
        status = stripped_msg + " " + url

    returncode = api.update_status(status)

    if returncode is None:
        message(str(returncode), target="GenPage")

