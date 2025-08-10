# engage_tests.py
# A simple test runner for the Engage language interpreter.
# This script executes all example files to check for runtime errors.

import sys
import io
from contextlib import redirect_stdout, redirect_stderr
import time

# We assume engage_lexer.py, engage_parser.py, and engage_vm.py are in the same directory.
# This requires the run() function and a fresh symbol table for each run.
from engage_vm import run, bootstrap_image

# --- Test Cases ---
# The source code for our example programs is stored here as multi-line strings.

FIBONACCI_CODE = """
// fibonacci.engage
to fibonacci with n:
    if n is less than 2 then
        return n.
    otherwise
        let a be fibonacci with n minus 1.
        let b be fibonacci with n minus 2.
        return a plus b.
    end
end
let result be fibonacci with 10.
"""

GUESS_THE_NUMBER_CODE = """
// guess_the_number.engage
// NOTE: This test is not fully automated due to user input.
// We are just checking if it runs without crashing.
print with "I'm thinking of a number between 1 and 100.".
let secret_number be 42.
// We will only loop once for the test.
let guess be 42. 
let user_input be "42".

if guess is not secret_number then
    print with "Test failed: Initial condition incorrect.".
end

if guess is secret_number then
    print with "You guessed it! The number was 42.".
end
"""

CONCURRENCY_CODE = """
// concurrency_demo.engage
create a channel named messages.
run concurrently:
    send "Hello" through messages.
    send "from" through messages.
    send "the" through messages.
    send "concurrent" through messages.
    send "task!" through messages.
    send "DONE" through messages.
end
let received_message be "".
while received_message is not "DONE":
    let received_message be receive from messages.
end
"""

RECORDS_CODE = """
// records_demo.engage
define a record named Vector2:
    let x be 0.
    let y be 0.
    to add with other:
        let new_x be self.x plus other.x.
        let new_y be self.y plus other.y.
        return new Vector2 with x: new_x, y: new_y.
    end
    to scale with factor:
        set self.x to self.x times factor.
        set self.y to self.y times factor.
    end
    to magnitude:
        let x_squared be self.x times self.x.
        let y_squared be self.y times self.y.
        return x_squared plus y_squared.
    end
end
let v1 be new Vector2 with x: 3, y: 4.
let v2 be new Vector2 with x: 1, y: 2.
let v3 be v1.add with v2.
v1.scale with 10.
let mag_sq be v1.magnitude.
"""

ERRORS_CODE = """
// error_handling_demo.engage
// Demonstrates the Result type and explicit error handling.
// This function tries to parse a number and propagates any error.
to parse_number with text:
    let result be number with text or return error.
    return Ok with result.
end

// --- Test Case 1: Successful Conversion ---
print with "Attempting to parse a valid number string...".
let good_result be parse_number with "123.45".
if good_result is an Error then
    print with "This should not happen!".
otherwise
    let final_number be the ok value of good_result.
    print with "Success! The number is:" concatenated with " " concatenated with final_number.
end

print with "". // Blank line for spacing

// --- Test Case 2: Failed Conversion ---
print with "Attempting to parse an invalid string...".
let bad_result be parse_number with "hello".

if bad_result is an Error then
    let error_message be the error message of bad_result.
    print with "Caught expected error: " concatenated with error_message.
otherwise
    print with "This should have failed!".
end
"""

# Comprehensive error handling tests covering all requirements
COMPREHENSIVE_ERROR_TESTS = """
// comprehensive_error_handling_tests.engage
// Tests all error handling requirements systematically

print with "=== Comprehensive Error Handling Tests ===".

// --- Requirement 1: number function behavior ---
print with "Testing number function behavior...".

// Test 1.1: Successful conversion
let success_result be number with "42.5".
if success_result is an Ok then
    let value be the ok value of success_result.
    print with "Test 1.1 PASS: number('42.5') returned Ok with value " concatenated with value.
otherwise
    print with "Test 1.1 FAIL: Expected Ok result".
end

// Test 1.2: Failed conversion
let fail_result be number with "invalid".
if fail_result is an Error then
    let error_msg be the error message of fail_result.
    print with "Test 1.2 PASS: number('invalid') returned Error with message: " concatenated with error_msg.
otherwise
    print with "Test 1.2 FAIL: Expected Error result".
end

// Test 1.3: No arguments (this will be tested in a separate function)
to test_number_no_args:
    let no_args_result be number.
    if no_args_result is an Error then
        let error_msg be the error message of no_args_result.
        print with "Test 1.3 PASS: number() with no args returned Error: " concatenated with error_msg.
    otherwise
        print with "Test 1.3 FAIL: Expected Error for no arguments".
    end
end
test_number_no_args.

// --- Requirement 2: or return error behavior ---
print with "Testing 'or return error' behavior...".

to test_error_propagation with input:
    let result be number with input or return error.
    return Ok with result.
end

// Test 2.1: Error propagation
let error_prop_result be test_error_propagation with "bad_input".
if error_prop_result is an Error then
    print with "Test 2.1 PASS: Error was properly propagated".
otherwise
    print with "Test 2.1 FAIL: Error should have been propagated".
end

// Test 2.2: Ok value continuation
let ok_prop_result be test_error_propagation with "123".
if ok_prop_result is an Ok then
    print with "Test 2.2 PASS: Ok value was properly handled".
otherwise
    print with "Test 2.2 FAIL: Ok value should have been handled".
end

// Test 2.3: Non-Result value continuation
to test_non_result_continuation:
    let value be 42 or return error.
    return Ok with value.
end
let non_result_test be test_non_result_continuation.
if non_result_test is an Ok then
    print with "Test 2.3 PASS: Non-Result value continued execution".
otherwise
    print with "Test 2.3 FAIL: Non-Result value should continue execution".
end

// --- Requirement 3: Type checking operators ---
print with "Testing type checking operators...".

// Test 3.1: Error is an Error
let error_val be Error with "test error".
if error_val is an Error then
    print with "Test 3.1 PASS: Error value correctly identified as Error".
otherwise
    print with "Test 3.1 FAIL: Error value should be identified as Error".
end

// Test 3.2: Ok is not an Error
let ok_val be Ok with 42.
if ok_val is an Error then
    print with "Test 3.2 FAIL: Ok value should not be identified as Error".
otherwise
    print with "Test 3.2 PASS: Ok value correctly not identified as Error".
end

// Test 3.3: Ok is an Ok
if ok_val is an Ok then
    print with "Test 3.3 PASS: Ok value correctly identified as Ok".
otherwise
    print with "Test 3.3 FAIL: Ok value should be identified as Ok".
end

// Test 3.4: Error is not an Ok
if error_val is an Ok then
    print with "Test 3.4 FAIL: Error value should not be identified as Ok".
otherwise
    print with "Test 3.4 PASS: Error value correctly not identified as Ok".
end

// Test 3.5: Non-Result is neither Error nor Ok
let regular_val be 42.
if regular_val is an Error then
    print with "Test 3.5a FAIL: Regular value should not be Error".
otherwise
    print with "Test 3.5a PASS: Regular value correctly not Error".
end

if regular_val is an Ok then
    print with "Test 3.5b FAIL: Regular value should not be Ok".
otherwise
    print with "Test 3.5b PASS: Regular value correctly not Ok".
end

// --- Requirement 4: Value extraction operators ---
print with "Testing value extraction operators...".

// Test 4.1: Extract value from Ok
let ok_with_value be Ok with "success".
let extracted_ok be the ok value of ok_with_value.
print with "Test 4.1 PASS: Extracted Ok value: " concatenated with extracted_ok.

// Test 4.3: Extract error message from Error
let error_with_msg be Error with "failure message".
let extracted_error be the error message of error_with_msg.
print with "Test 4.3 PASS: Extracted Error message: " concatenated with extracted_error.

// --- Requirement 5: Result constructors ---
print with "Testing Result constructors...".

// Test 5.1: Ok with value
let ok_construct be Ok with 123.
if ok_construct is an Ok then
    let val be the ok value of ok_construct.
    print with "Test 5.1 PASS: Ok constructor with value works, value: " concatenated with val.
otherwise
    print with "Test 5.1 FAIL: Ok constructor failed".
end

// Test 5.2: Error with value
let error_construct be Error with "test error".
if error_construct is an Error then
    let msg be the error message of error_construct.
    print with "Test 5.2 PASS: Error constructor with value works, message: " concatenated with msg.
otherwise
    print with "Test 5.2 FAIL: Error constructor failed".
end

// Test 5.3: Ok without value
let ok_no_val be Ok.
if ok_no_val is an Ok then
    print with "Test 5.3 PASS: Ok constructor without value works".
otherwise
    print with "Test 5.3 FAIL: Ok constructor without value failed".
end

// Test 5.4: Error without value
let error_no_val be Error.
if error_no_val is an Error then
    print with "Test 5.4 PASS: Error constructor without value works".
otherwise
    print with "Test 5.4 FAIL: Error constructor without value failed".
end

print with "=== End Comprehensive Error Handling Tests ===".
"""

# Edge case tests for error handling
ERROR_EDGE_CASES = """
// error_edge_cases.engage
// Tests edge cases and error conditions

print with "=== Error Handling Edge Cases ===".

// Test nested error handling
to nested_error_test with input:
    to inner_function with val:
        let result be number with val or return error.
        return Ok with result.
    end
    
    let inner_result be inner_function with input or return error.
    let final_value be the ok value of inner_result.
    return Ok with final_value.
end

// Test successful nested case
let nested_success be nested_error_test with "42".
if nested_success is an Ok then
    print with "Nested success test PASS".
otherwise
    print with "Nested success test FAIL".
end

// Test failed nested case
let nested_fail be nested_error_test with "invalid".
if nested_fail is an Error then
    print with "Nested failure test PASS".
otherwise
    print with "Nested failure test FAIL".
end

// Test multiple error propagation in sequence
to multi_error_test:
    let first be number with "10" or return error.
    let second be number with "20" or return error.
    let third be number with "invalid" or return error.
    // This line should never execute
    print with "This should not print".
    return Ok with third.
end

let multi_result be multi_error_test.
if multi_result is an Error then
    print with "Multiple error propagation test PASS".
otherwise
    print with "Multiple error propagation test FAIL".
end

print with "=== End Edge Cases ===".
"""

# --- Test Runner ---

def run_test(name, code):
    """
    Runs a single test case.
    - Creates a fresh environment for each test.
    - Captures stdout and stderr to check for errors.
    - Returns True on success, False on failure.
    """
    print(f"--- Running test: {name} ---")
    
    # Redirect stdout/stderr to capture output and errors
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    # Each test gets a clean, fresh environment
    test_symbol_table = bootstrap_image()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            run(code, test_symbol_table)
        
        # Check if any errors were printed to stderr
        error_output = stderr_capture.getvalue()
        if error_output:
            print(f"FAIL: {name}")
            print("--- Error Output ---")
            print(error_output)
            return False
        
        print(f"PASS: {name}")
        return True
        
    except Exception as e:
        print(f"FAIL: {name}")
        print(f"An unexpected Python exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    tests = {
        "Fibonacci Example": FIBONACCI_CODE,
        "Guess the Number Example": GUESS_THE_NUMBER_CODE,
        "Concurrency Example": CONCURRENCY_CODE,
        "Records and Methods Example": RECORDS_CODE,
        "Types and Errors Example": ERRORS_CODE,
        "Comprehensive Error Handling Tests": COMPREHENSIVE_ERROR_TESTS,
        "Error Handling Edge Cases": ERROR_EDGE_CASES,
    }
    
    passed_count = 0
    failed_count = 0
    
    for name, code in tests.items():
        if run_test(name, code):
            passed_count += 1
        else:
            failed_count += 1
        print("-" * 30)

    # The concurrency test involves threads that might not finish instantly.
    # A small delay helps ensure the main thread doesn't exit before they run.
    print("Waiting for any background tasks to complete...")
    time.sleep(0.1) 
    
    print("\n--- Test Summary ---")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    
    if failed_count > 0:
        sys.exit(1)
    else:
        print("All tests passed successfully!")
        sys.exit(0)
