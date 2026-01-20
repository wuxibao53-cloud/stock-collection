import os
import pytest
from full_a_stock_collector import MultiSourceCollector, DEFAULT_UAS


def test_force_ua_env(monkeypatch):
    monkeypatch.setenv('FORCE_UA', 'MyBot/1.0')
    c = MultiSourceCollector(db_path='/tmp/test_config.db')
    assert c.headers['User-Agent'] == 'MyBot/1.0'


def test_proxy_env(monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:8888')
    monkeypatch.setenv('HTTPS_PROXY', 'https://127.0.0.1:8889')
    c = MultiSourceCollector(db_path='/tmp/test_config.db')
    assert 'http' in c.proxies and 'https' in c.proxies
    assert c.session.proxies.get('http') == 'http://127.0.0.1:8888'


def test_retry_adapter():
    c = MultiSourceCollector(db_path='/tmp/test_config.db')
    adapter = c.session.adapters.get('https://')
    assert adapter is not None
    # adapter has max_retries attribute
    assert hasattr(adapter, 'max_retries')
    assert getattr(adapter, 'max_retries').total >= 3
