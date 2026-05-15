from src.greeter import greet

def test_greet_normal():
    assert greet("Alice") == "Hello, Alice!"

def test_greet_empty():
    assert greet("") == "Hello, stranger!"

def test_greet_none():
    assert greet(None) == "Hello, stranger!"
