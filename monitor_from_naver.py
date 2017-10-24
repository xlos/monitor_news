#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import datetime
import io
import os
import json
import requests
import base64
import sys
import re
import traceback

import urllib2, urllib
from bs4 import BeautifulSoup
from urlparse import urljoin


class Crawl:
    delayTime=1
    
    def __init__(self):
        self.already_posted = set()
    @classmethod
    def make_links_absolute(self, soup, url):
        for tag in soup.findAll('a', href=True):
            try:
              tag['href'] = urljoin(url, tag['href'].split("#")[0])
            except:
              print "make_links_absolute_error" + tag['href']
    @classmethod
    def crawl(self, url, encode='utf8'):
        retry = 0
        html = '<html></html>'
        while True:
            try :
                #url = urllib.quote(url.encode('utf8'), '/:')
                retry += 1
                if retry > 2:
                  print 'Error wait %d sec %s'%(self.delayTime, url.encode('utf8'))
                  break
                html = urllib2.urlopen(url).read().decode(encode, 'ignore')
            except:
                url = urllib.quote(url.encode('utf8'), '/:')
                time.sleep(self.delayTime)
                traceback.print_exc()
                continue
            break
        return html
 
    @classmethod
    def crawl_and_parse(self, url, encode='utf8'):
        html = Crawl.crawl(url, encode)
        soup = BeautifulSoup(html, "html.parser")
        self.make_links_absolute(soup, url)
        return soup
    def encode(self, word, encoding='euc-kr'):
        #네이버 뉴스는 url을 한글로 encoding함 -_-;
        return urllib.quote_plus(word.decode('utf-8').encode(encoding))
    def filter_title(self, title):
        title = title.replace('<', ' ')
        return title.replace('>', ' ')
    def generate_naver_search_url(self, term):
        query = self.encode(term.strip(), 'utf8')
        return "https://search.naver.com/search.naver?where=news&query=%s&ie=utf8&sm=tab_srt&sort=1&photo=0&field=0&reporter_article=&pd=0&ds=&de=&docid=&mynews=0&mson=0&refresh_start=0&related=0" % query
    def generate_naver_blog_search_url(self, term, start=0):
        query = self.encode(term.strip(), 'utf8')
        if start > 1:
          return "https://search.naver.com/search.naver?where=post&sm=tab_pge&query=%s&st=sim&date_option=0&date_from=&date_to=&dup_remove=1&post_blogurl=tistory.com&post_blogurl_without=&srchby=all&nso=&ie=utf8&start=%d"%(query, start)
        return "https://search.naver.com/search.naver?where=post&query=%s&ie=utf8&st=sim&sm=tab_opt&date_from=&date_to=&date_option=0&srchby=all&dup_remove=1&post_blogurl=tistory.com&post_blogurl_without=&mson=0"%query 


    def search_from_naver_news(self, keyword):
        url = self.generate_naver_search_url(keyword)
        print url
        return self.crawl_and_parse(url, 'utf8')
    def search_from_naver_blog(self, keyword, start=0):
        url = self.generate_naver_blog_search_url(keyword, start)
        return self.crawl_and_parse(url, 'utf8')
 
    def get_blog_search_results(self, soup):
        data = soup.select('div.blog ul li.sh_blog_top')
        result = []
        for d in data:
            r = {}
            try:
                r['title'] = self.filter_title(d.select('a.sh_blog_title')[0].get_text().encode('utf8'))
                r['outlink'] = d.select('a.url')[0]['href'].encode('utf8')
                r['url'] = r['outlink']
                r['press'] = d.select('a.txt84')[0].get_text().encode('utf8')
                r['desc'] = d.select('dd.sh_blog_passage')[0].get_text().strip().encode('utf8')
                imgs = d.select('img.sh_blog_thumbnail')
                if len(imgs) > 0:
                    r['img'] =  imgs[0]['src'].encode('utf8')
                r['info'] = ''
            except:
                print 'error'
                None
            result.append(r)
        return result
 
    def get_search_results(self, soup):
        data = soup.select('div.news.mynews.section ul li')
        result = []
        for d in data:
            r = {}
            try:
                r['title'] = self.filter_title(d.select('a._sp_each_title')[0].get_text().encode('utf8'))
                r['url'] = d.select('a._sp_each_title')[0]['href'].encode('utf8')
                r['outlink'] = d.select('a._sp_each_title')[0]['href'].encode('utf8')
                r['press'] = d.select('span._sp_each_source')[0].get_text().encode('utf8')
                #use naver news url instead of the original news site url
                arr = d.select('dd.txt_inline a._sp_each_url')
                if len(arr) > 0:
                    r['url'] = arr[0]['href'].encode('utf8')
                r['desc'] = d.select('dl dd')[1].get_text().strip().encode('utf8')
                imgs = d.select('a.sp_thmb img')
                if len(imgs) > 0:
                    r['img'] =  imgs[0]['src'].encode('utf8')
                r['info'] =' | %s' %(r['press'])
                r['info'] = '| %s' % self.filter_title( d.select('dd.txt_inline')[0].get_text().encode('utf8'))
            except:
                continue
            result.append(r)
        return result
    def filter_search_results(self, before, after):
        result = []
        for d in before:
            self.already_posted.add( d['url'] )
        for d in after:
            if d['url'] in self.already_posted:
                continue
            result.append(d)
            self.already_posted.add( d['url'] )
        return result
    def save_to_file(self, fname, contents):
        f = open(fname, 'w')
        f.write(contents)
        f.close()
    def find_recent_news(self, keyword, prefix='./keyword'):
        soup = self.search_from_naver_news(keyword)
        new_results = self.get_search_results(soup)
        print "search %d results for keyword %s" % (len(new_results), keyword)
        fname = "%s_%s" %(prefix, base64.urlsafe_b64encode(keyword))
        try:
            before_results = self.get_search_results(BeautifulSoup(io.open(fname, 'r', encoding='utf8')))
        except:
            before_results = []
        self.save_to_file(fname, str(soup))
        return self.filter_search_results(before_results, new_results)
    def send_news(self, keyword, results, urls):
        count = 0
        msg = '===== %s =====\n' %(keyword)
        for r in results:
            if 'img' in r:
                #msg += '%s\n' % r['img']
                None
            msg += "%02d. <%s|%s>%s\n" %(count+1, r['url'], r['title'], r['info'])
            msg += "%s\n" %(r['desc'])
            count +=1
        if count > 0:
            url = self.generate_naver_search_url(keyword)
            msg += "search results for <%s|%s>\n" % (url,keyword)
            for url in urls: 
                self.send_to_slack(msg, url)
        return count
    def send_to_slack(self,msg, url):
        if msg is None:
            return
        #msg +='powered by Dable'
        payload = {
            "text":msg,
            "username": "naver-news-bot",
            "icon_emoji": ":newspaper:"
        }
        r = requests.post(url, data=json.dumps(payload))
        print r.text
    def monitor(self, urls, keywords):
        sended = 0 
        for keyword in keywords:
            news_list = self.find_recent_news(keyword)
            sended += self.send_news(keyword, news_list, urls)
        return sended
 
if __name__ == '__main__':
    crawler = Crawl()
    #urls = ['https://hooks.slack.com/services/########']
    urls = []
    if len(urls) == 0:
        print "please set slack hook urls"
        sys.exit(1)
    if len(sys.argv) > 1:
        urls = sys.argv[1].split(",")
    keywords = ['데이블']
    if len(sys.argv) > 2:
        keywords = " ".join(sys.argv[2:]).split(",")
    crawler.monitor(urls, keywords)

