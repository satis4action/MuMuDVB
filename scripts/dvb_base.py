#! /usr/bin/env python
# -*- coding: iso8859-15 -*-

""" Configuration de base des diff�rents transpondeurs disponibles """

#Auteur : Fr�d�ric Pauget
#Maintenance et adaptations : DUBOST Brice
#Licence : GPLv2

from commands import getoutput
from time import sleep
import os, socket

IP = socket.gethostbyaddr(socket.gethostname())[-1][0]

class CarteOqp(Exception) :
    """ La carte est d�ja utilis�e """

class NotRunning(Exception) :
    """ La carte ne diffuse rien """
    
class carte :
    """ Classe parent de toute classe de transpondeur """
    # Niveux de verbosite :
        # 0 : ne dit rien
        # 1 : messages � caract�res informatifs
        # 2 : messages de debug
        # 3 : ne permet pas � mumudvb de daemonizer
    verbose = 3
    
    CONF_FILE = "/etc/sat/carte%i.conf" # %i : numero de la carte
    
    timeout_accord=20 #en secondes
    timeout_no_diff=60 #en secondes
    
    entete_conf = """### Fichier g�n�r�, NE PAS EDITER
freq=%(freq)i
pol=%(pol)s
srate=%(srate)i
card=%(card)i
timeout_accord=%(timeout_accord)i
timeout_no_diff=%(timeout_no_diff)i
"""

    entete_conf_TNT = """### Fichier g�n�r�, NE PAS EDITER
freq=%(freq)i
qam=%(qam)s
trans_mode=%(trans_mode)s
bandwidth=%(bandwidth)s
guardinterval=%(guardinterval)s
coderate=%(coderate)s
card=%(card)i
timeout_accord=%(timeout_accord)i
timeout_no_diff=%(timeout_no_diff)i
"""

    chaine_template = """ip=%(ip)s
port=1234
name=%(name)s
pids=%(pids)s
"""

    pid_file = "/var/run/mumudvb/mumudvb_carte%i.pid" # % num carte
    mumudvb = "/usr/local/bin/mumudvb "
    
    def __cmp__(a,b) :
        for attr in ( 'card', 'freq', 'chaines' ) :
            if getattr(a,attr) != getattr(b,attr) :
                return -2
        return 0
    
    def __init__(self,card) :
        """ Initalisation card est le num�ro (entier) de la carte 
        correspondante """
        try :
            self.freq = int(str(self.__class__).split('_')[-1])
        except :
            # On ne pourra pas faire grand chose � part killer le flux de la carte
            self.freq = ''
            pass
        self.card = card
                
    def gen_conf(self) :
        """ G�n�re le fichier de conf """
        if not self.freq : 
            if self.verbose > 1 : print "Instance ne permettant pas la g�n�ration de la conf"
            return
        
        fd = open(self.CONF_FILE % self.card,'w')
        # Ent�te du fichier
        try:
            fd.write( self.entete_conf_TNT % 
                      { 'qam' : self.qam, 'trans_mode' : self.trans_mode ,
                        'bandwidth' : self.bandwidth, 'guardinterval' : self.guardinterval ,
                        'coderate' : self.coderate,
                        'freq' : self.freq , 'card' : self.card ,
                        'timeout_accord' : self.timeout_accord ,
                        'timeout_no_diff' : self.timeout_no_diff } )
        except:
            fd.write( self.entete_conf % 
                      { 'pol' : self.pol, 'srate' : self.srate ,
                        'freq' : self.freq , 'card' : self.card ,
                        'timeout_accord' : self.timeout_accord ,
                        'timeout_no_diff' : self.timeout_no_diff } )

        # Chaines
        n = 0
        for pids, name in self.chaines.items() :
            ip = '239.%s.20%i.2%02i' % ( IP.split('.')[-1], self.card, n)
            n += 1
            fd.write(self.chaine_template % vars())
        fd.close()
    
    def get_pid(self) :
        """ Retourne le pid associ� � la carte """
        try:
            pid = int(open(self.pid_file % self.card).readline().strip())
            if self.verbose > 1 :
                print 'pid : %i' % pid ,
            return pid
        except :
            raise NotRunning
            
    def is_running(self) :
        """ V�rifie si le process correspondant � la carte toune """
        if self.verbose > 1 :
            redir = ''
        else :
            redir = '>/dev/null 2>&1'
        try :
            if not os.system('ps %i %s' % (self.get_pid() , redir) ) :
                # Il tourne
                return True
        except NotRunning :
            pass
        return False
    
    def start(self) :
        """ Lance la diffusion """
        if not self.freq : 
            if self.verbose > 1 : print "Instance ne permettant pas le lancement d'un flux"
            return
        
        if self.verbose >0 :
            print "Lancement de %s sur la carte %i" % (str(self.__class__).split('.')[-1], self.card)
            
        if self.is_running() :
            raise CarteOqp
        
        if self.verbose >0 : print "\tG�n�ration de la conf...",
        self.gen_conf()
        if self.verbose >0 : print "OK"
        
        cmd = '%s -c %s' % ( self.mumudvb, self.CONF_FILE % self.card )
        if self.verbose > 2 : cmd += ' -d -s'
        if self.verbose > 1 :
            print "\tCommande : %s" % cmd
        for i in range(2*self.timeout_accord) :
            if not i%5 and i <= self.timeout_accord :
                if self.verbose > 0 and i : print "ATTENTE/ERREUR"
                # On fait une tentative de lancement toutes les 5s (en cas de pb de diseq)        
                if self.verbose > 0 : print "\tTentative %i" %(i/5+1) ,
                os.system(cmd)
            sleep(1)
            if self.is_running() :
                if self.verbose > 0 : print 'OK'
                break
        sleep(1)
        if not self.is_running() :
            if self.verbose > 0 : print 'ABANDON'
            raise NotRunning
            
    def stop(self) :
        """ Arr�te la diffusion de la carte """
        if self.verbose >0 : 
            print "Arret diffusion carte %i..." % self.card ,
            
        try : 
            # Ca tourne au moins ?
            if not self.is_running() : 
                if self.verbose >0 : print "carte d�ja arr�t�e"
                return
            
            os.kill(self.get_pid(),15)
            sleep(1)
            if not self.is_running() : 
                if self.verbose >0 : print "OK"
                return
            
            # Cr�ve !!
            if not self.is_running() : 
                if self.verbose >0 : print "SIGKILL"
                return
            
            os.kill(self.get_pid(),9)
            # Salloperie
            raise CarteOqp
        except NotRunning :
            # Parfait, c'�tait le but
            pass
        
    def restart(self) :
        """ Red�marre le flux """
        self.stop()
        self.start()
    
class Hotbird_10796(carte) :
    pol='v'
    srate=27500
    chaines = {
       '3534 3504' : 'rad fra France Inter',
       '3535 3505' : 'rad fra France Info' }

class Hotbird_10873(carte) :
    pol='v'
    srate=27500
    chaines = {
       '3101 3131' : 'rad fra Europe 1',
       '3102 3132' : 'rad fra Europe 2',
       '3103 3133' : 'rad fra RFM',
       '3105 3135' : 'rad fra RTL',
       '3106 3136' : 'rad fra NRJ',
       '3107 3137' : 'rad fra Radio Classique',
       '3108 3138' : 'rad fra Cherie FM',
       '3111 3141' : 'rad fra HITWEST',
       '3202 3232' : 'rad fra Rires et chansons',
       '3210 3240' : 'rad fra Nostalgie',
       '4100 4130' : 'rad fra GUIDE' }

class Hotbird_10911(carte) :
    pol='v'
    srate=27500
    chaines = {
       '3207 3237' : 'rad fra RFI',
       '3301 3331' : 'rad fra Beur FM',
       '3501 3531' : 'rad fra France Musiques',
       '3503 3533' : 'rad fra FIP',
       '3506 3536' : 'rad fra France Culture',
       '3508 3538' : 'rad fra Le Mouv',
       '5801 5831' : 'rad fra Meteo Express',
       '7500 7530' : 'rad fra PLAYIN TV' }

class Hotbird_11137(carte) :
    pol='h'
    srate=27500
    chaines = {
       '524 644 260' : 'fra Beur TV',
       '3521 3641 717 3601' : 'fra TV5 FBS',
       '3522 3642 719 3602' : 'fra TV5 Europe',
       '3523 3643 265' : 'ita Roma uno',
       '3524 3644 262' : 'ara ANN',
       '3525 3645 267' : 'ita Videolook',
       '3526 3646 263' : 'ara K-TV',
       '3528 3648 264' : 'ita Videolina',
       '3529 3649 258' : 'ita TeleGenova Sat 2',
       '3531 3651 261' : 'ita Amica9 telestar' }

class Hotbird_11200(carte) :
    pol='V'
    srate=27500
    chaines = {
       '366 367 2560' : 'ita Elite shopping TV',
       '382 383 768' : 'ita calabria sat',
       '386 387 512' : 'x-ero tv conto',
       '397 398 399' : 'ita starsat',
       '382 383 2048' : 'ita italia.tv channel',
       '394 395 394' : 'x-ero play TV',
       '400 401 402' : 'ita people tv',
       '405 406 407' : 'ita roma sat',
       '413 414 415' : 'ita sat adriatico' }

class Hotbird_11242(carte) :
    pol='v'
    srate=27500
    chaines = {
       '121 122 123' : 'ita TV7 Lombardia',
       '3011 3012 3010' : 'fra TV8 Mont Blanc',
       '33 36 35 500' : 'fra HD Forum',
       '308 256 257' : 'fra World Fashion Channel' }

class Hotbird_11304(carte) :
    pol='h'
    srate=27500
    chaines = {
       '1060 1020 210' : 'esp venevision continental',
       '310 256 211' : 'esp TV Chile',
       '513 514 212' : 'esp TV Colombia'}

class Hotbird_11604(carte) :
    pol='h'
    srate=27500
    chaines = {
       '172 173 600 174' : 'ger Das Erste',
       '1000 1001 700' : 'ger DW TV',
       '175 176 900 177' : 'ger RTL2 Schweiz',
       '180 181 1100 182' : 'ger SUPER RTL Schweiz',
       '190 191 1200' : 'pol Viva Polska' }

class Hotbird_11623(carte) :
    pol='v'
    srate=27500
    chaines = {
       '230 250 210 297' : 'fra 123 sat',
       '225 245 205' : 'fra Best Of Shopping',
       '221 241 201' : 'x-ero Videosexy TV',
       '231 251 32' : 'x-ero SexySat 3',
       '227 247 207 287' : 'rom TV romania'}

class Hotbird_11642(carte) :
    pol='h'
    srate=27500
    chaines = {
       '1360 1320 5003' : 'eng Bloomberg Europe',
       '1460 1420 5004' : 'ger Bloomberg TV Deutschland',
       '1560 1520 5005' : 'eng Bloomberg U.K.' }

class Hotbird_11727(carte) :
    pol='v'
    srate=27500
    chaines = {
       '2711 2712 257' : 'fra la locale',
       '2730 2731 2732 264' : 'ara Al Maghribiyah',
       '2741 2742 265' : 'ita Sicilia International (SET)',
       '2751 2752 266' : 'ita Sardegna Uno Sat'}
       
class Hotbird_11785(carte) :
    pol='h'
    srate=27500
    chaines = {
       '3521 3522 3520 3525' : 'esp TVE International',
       '3569 3570 3568 3573' : 'esp Canal 24 Horas',
       '3553 3554 3552' : 'esp TVE Internacional Asia/Africa' }

class Hotbird_12245(carte) :
    pol='h'
    srate=27500
    chaines = {
       '127 137 117' : 'fra TELIF',
       '128 138 32' : 'x-ero sexysat',
       '1023 1033 1014' : 'fra astro center TV' }

class Hotbird_12476(carte) :
    pol='h'
    srate=27500
    chaines = {
       '101 201 202 203 204 205 206 207 208 209 210 211 212 100' : 'vo autres  EBS',
       '101 203 100' : 'fra EBS',
       '601 602 257' : 'ara 2M',
       '551 552 550' : 'x-ero X Stream'}

class Hotbird_12558(carte) :
    pol='v'
    srate=27500
    chaines = {
       '6660 6661 6659' : 'ita Administra.it',
       '6916 6917 6915 6930' : 'ita 24 Ore' }

class Hotbird_12577(carte) :
    pol='h'
    srate=27500
    chaines = {
       '1204 1304 1104' : 'fra telesud',
       '1206 1306 1106' : 'fra F men',
       '1218 1313 33 34' : 'x-ero sexysat1',
       '1206 1306 1106' : 'x-ero Full X 4 free',
       '1209 1309 1109' : 'fra liberty TV',
       '1239 1339 1139' : 'ned liberty TV' }

class Hotbird_12597(carte) :
    pol='v'
    srate=27500
    chaines = {
       '80 81 1024' : 'rus sport planeta',
       '163 92 1027' : 'eng BBC World',
       '167 108 1031' : 'rus ORT International',
       '2221 2231 2232 2233 2234 2235 2236 2237 2238 1034 768' : 'fra autres Euronews',
       '2221 2232 1034 768' : 'eng Euronews' }

class TNT_base(carte) :
    qam="auto"
    trans_mode="auto"
    guardinterval="auto"
    coderate="auto"
    bandwidth="8MHz"
    
class TNT_R1_586000(TNT_base) :
    chaines = {
       '120 130 110' : 'fra TNT02 France 2',
       '210 220 230' : 'fra TNT03 France 3',
       '410 420 430' : 'fra TNT14 France 4',
       '310 320 330' : 'fra TNT05 France 5',
       '510 520 530' : 'fra TNT07 Arte',
       '510 520 531' : 'ger Arte',
       '610 620 630' : 'fra TNT13 LCP Public Senat' }

class TNT_R2_474000(TNT_base) :
    chaines = {
       '160 80 1280' : 'fra TNT08 Direct 8',
       '161 84 1281' : 'fra TNT10 TMC',
       '162 88 1282' : 'fra TNT15 BFM TV',
       '163 92 1283' : 'fra TNT16 i tele',
       '164 96 1284' : 'fra TNT17 europe2 TV',
       '165 100 1285' : 'fra TNT18 Gulli'}

class TNT_R3_522000(TNT_base) :
    chaines = {
       '160 170 120 1280' : 'fra TNT04 Canal'}

class TNT_R4_498000(TNT_base) :
    chaines = {
       '120 130 110'  : 'fra TNT06 M6',
       '220 230 210'  : 'fra TNT09 W9',
       '320 330 310' : 'fra TNT11 NT1'}

class TNT_R6_562000(TNT_base) :
    chaines = {
       '120 130 100'  : 'fra TNT01 TF1',
       '220 230 231 200'  : 'fra TNT12 NRJ12'}
