import sys
sys.path.append('.')

from bot import apply_provider

# Test cases from test_apply_provider_edge_cases
print("Testing apply_provider with unsupported provider...")

# Test with unsupported provider (should return original URL)
result1 = apply_provider("http://example.com/test", "unsupported_provider", "anykey")
expected1 = "http://example.com/test"
print(f"Test 1 - Unsupported provider: {result1 == expected1} (got: {result1}, expected: {expected1})")

# Test with unsupported provider key
result2 = apply_provider("http://example.com/test", "twitter", "unsupported_key")
expected2 = "http://example.com/test"
print(f"Test 2 - Unsupported provider key: {result2 == expected2} (got: {result2}, expected: {expected2})")

# Test with malformed URL
result3 = apply_provider("not-a-url", "twitter", "vx")
expected3 = "not-a-url"
print(f"Test 3 - Malformed URL: {result3 == expected3} (got: {result3}, expected: {expected3})")

# Test empty strings
result4 = apply_provider("", "twitter", "vx")
expected4 = ""
print(f"Test 4 - Empty URL: {result4 == expected4} (got: '{result4}', expected: '{expected4}')")

result5 = apply_provider("http://example.com", "", "vx")
expected5 = "http://example.com"
print(f"Test 5 - Empty provider key: {result5 == expected5} (got: {result5}, expected: {expected5})")

# Test a valid case to make sure we didn't break anything
result6 = apply_provider("http://twitter.com/user/status/123", "twitter", "vx")
expected6 = "http://vxtwitter.com/user/status/123"
print(f"Test 6 - Valid provider: {result6 == expected6} (got: {result6}, expected: {expected6})")

print("All tests completed!")