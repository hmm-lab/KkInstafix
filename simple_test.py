# Simple test to verify basic functionality
import sys
print("Python version:", sys.version)

# Try to import bot
try:
    sys.path.append('.')
    import bot
    print("Successfully imported bot")

    # Test the apply_provider function
    result = bot.apply_provider("http://example.com/test", "unsupported_provider", "anykey")
    print(f"apply_provider with unsupported provider: {result}")
    assert result == "http://example.com/test", f"Expected original URL, got {result}"

    # Test a valid provider
    result2 = bot.apply_provider("http://twitter.com/user/status/123", "twitter", "vx")
    print(f"apply_provider with twitter vx: {result2}")
    assert result2 == "http://vxtwitter.com/user/status/123", f"Expected converted URL, got {result2}"

    print("All basic tests passed!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()