# -*- coding: utf-8 -*-
from django.test import TestCase
from django.db import models
from parser import VkontakteParser
from models import VkontakteIDModel, VkontakteManager
from utils import api_call, VkontakteError

class User(VkontakteIDModel):
    screen_name = models.CharField(u'Короткое имя группы', max_length=50, db_index=True)
    slug_prefix = ''

    remote = VkontakteManager()

class VkontakteApiTest(TestCase):

    def test_parse_page(self):

        parser = VkontakteParser()
        parser.content = '<!><!><!><!><!><div>%s</div>' % '1<!-- ->->2<!-- -<>->3<!-- -->4'

        self.assertEqual(parser.html, '<div>1234</div>')

    def test_resolvescreenname(self):

        response = api_call('resolveScreenName', screen_name='durov')
        self.assertEqual(response, {u'object_id': 1, u'type': u'user'})
        # fail with VkontakteError, when call with integer screen_name
        with self.assertRaises(VkontakteError):
            response = api_call('resolveScreenName', screen_name='0x1337')

        instance = User.remote.get_by_slug('durov')
        self.assertEqual(instance.remote_id, 1)

        instance = User.remote.get_by_slug('0x1337')
        self.assertEqual(instance, None)

    def test_requests_limit_per_sec(self):
        for i in range(0,20):
            api_call('resolveScreenName', screen_name='durov')