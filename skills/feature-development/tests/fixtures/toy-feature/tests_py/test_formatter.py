from src.formatter import format_greeting

def test_upper():
    assert format_greeting("alice", "upper") == "HELLO, ALICE!"

def test_lower():
    assert format_greeting("Alice", "lower") == "hello, alice!"

def test_title():
    assert format_greeting("alice", "title") == "Hello, Alice!"
