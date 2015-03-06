import hashlib
import logging
import xml.etree.ElementTree as Et
from tornado.options import options
from tornado.web import HTTPError
from handlers.base import BaseHandler
from libs.shadowsocks import Shadowsocks

__author__ = 'czbix'


class WeiXinHandler(BaseHandler):
    FROM_USER_TAG = 'FromUserName'
    TO_USER_TAG = 'ToUserName'
    CREATE_TIME_TAG = 'CreateTime'
    MSG_TYPE_TAG = 'MsgType'
    CONTENT_TAG = 'Content'
    EVENT_TAG = 'Event'
    EVENT_KEY_TAG = 'EventKey'

    CLICK_EVENT = 'CLICK'
    SUBSCRIBE_EVENT = 'subscribe'
    UNSUBSCRIBE_EVENT = 'unsubscribe'

    GET_PWD_EVENT_KEY = 'getPwd'

    def prepare(self):
        if not self._check_sign():
            if options.debug:
                logging.warning('invalid signature')
            else:
                raise HTTPError(401, 'invalid signature')

    def get(self):
        echostr = self.get_query_argument('echostr')
        self.write(echostr)

    def _check_sign(self):
        timestamp = self.get_query_argument('timestamp')
        nonce = self.get_query_argument('nonce')
        signature = self.get_query_argument('signature')

        calc_sign = hashlib.sha1(''.join(sorted([options.wx_token, timestamp, nonce])).encode()).hexdigest()

        return signature == calc_sign

    def post(self):
        tree = Et.fromstring(self.request.body)

        from_user = tree.find(self.FROM_USER_TAG).text
        to_user = tree.find(self.TO_USER_TAG).text
        msg_type = tree.find(self.MSG_TYPE_TAG).text
        # create_time = int(tree.find(self.CREATE_TIME_TAG).text)

        if msg_type == 'text' and self._handle_text_msg(tree, from_user, to_user):
            return
        elif msg_type == 'event' and self._handle_event_msg(tree, from_user, to_user):
            return
        else:
            logging.debug('received unknown msg, msg_type: ' + msg_type)

        self._unknown_msg(from_user, to_user)

    def _handle_text_msg(self, tree, from_user, to_user):
        content = tree.find(self.CONTENT_TAG).text
        logging.debug('received text msg, content: ' + content)

        return False

    @staticmethod
    def _build_ss_info():
        ss = Shadowsocks.find_latest(Shadowsocks.workers)
        if not ss.running:
            ss.start()

        content = 'Id: %d\n' \
                  'Port: %d\n' \
                  'Password: %s' \
                  % (ss.index, ss.port, ss.password)

        return content

    def _handle_event_msg(self, tree, from_user, to_user):
        event = tree.find(self.EVENT_TAG).text
        if event == self.UNSUBSCRIBE_EVENT:
            # there is nothing we can do
            return True

        if event == self.SUBSCRIBE_EVENT:
            self.write(self._build_text_reply(to_user, from_user, '谢谢关注喵~'))
            return True

        if event == self.CLICK_EVENT:
            event_key = tree.find(self.EVENT_KEY_TAG).text
            if event_key == self.GET_PWD_EVENT_KEY:
                self.write(self._build_text_reply(to_user, from_user, self._build_ss_info()))
                return True

        return False

    def _unknown_msg(self, from_user, to_user):
        random_texts = ['What does the fox say',
                        'Do you want to build a snowman',
                        'Let it go',
                        'You belong with me',
                        'Just one last dance',
                        'If I were a boy',
                        'Nothing else I can say',
                        '恋は渾沌の隷也',
                        '残酷な天使のテーゼ',
                        '恋爱サーキュレーション',
                        'ワールドイズマイン']

        import random

        self.write(self._build_text_reply(to_user, from_user, random.choice(random_texts)))

    @classmethod
    def _build_text_reply(cls, from_user, to_user, content):
        builder = Et.TreeBuilder()
        builder.start('xml')

        import time

        for tag, value in [(cls.TO_USER_TAG, to_user), (cls.FROM_USER_TAG, from_user),
                           (cls.CREATE_TIME_TAG, str(int(time.time()))), (cls.MSG_TYPE_TAG, 'text'),
                           (cls.CONTENT_TAG, content)]:
            builder.start(tag)
            builder.data(value)
            builder.end(tag)

        builder.end('xml')
        return Et.tostring(builder.close(), 'utf-8')
