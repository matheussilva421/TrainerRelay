#include "input_helper.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TEST_MAX_SEND_CALLS 8
#define TEST_MAX_EVENTS 8
#define FAKE_ACCEPT_ALL UINT_MAX

typedef struct {
    UINT requested;
    UINT accepted;
    INPUT events[TEST_MAX_EVENTS];
} FakeSendCall;

static FakeSendCall g_calls[TEST_MAX_SEND_CALLS];
static UINT g_call_count;
static DWORD g_sleep_ms;
static UINT g_configured_accepts[TEST_MAX_SEND_CALLS];

static void fail_test(const char *message, int line)
{
    fprintf(stderr, "FAIL line %d: %s\n", line, message);
    exit(1);
}

#define ASSERT_TRUE(condition) \
    do { \
        if (!(condition)) { \
            fail_test(#condition, __LINE__); \
        } \
    } while (0)

#define ASSERT_EQ_UINT(expected, actual) \
    do { \
        UINT expected_value = (expected); \
        UINT actual_value = (actual); \
        if (expected_value != actual_value) { \
            fprintf(stderr, "FAIL line %d: expected %u, got %u\n", __LINE__, expected_value, actual_value); \
            exit(1); \
        } \
    } while (0)

static void reset_fake(void)
{
    UINT index;

    memset(g_calls, 0, sizeof(g_calls));
    for (index = 0; index < TEST_MAX_SEND_CALLS; ++index) {
        g_configured_accepts[index] = FAKE_ACCEPT_ALL;
    }
    g_call_count = 0;
    g_sleep_ms = 0;
}

static UINT WINAPI fake_send_input(UINT count, LPINPUT events, int size)
{
    UINT accepted;

    ASSERT_TRUE(g_call_count < TEST_MAX_SEND_CALLS);
    ASSERT_EQ_UINT((UINT)sizeof(INPUT), (UINT)size);
    ASSERT_TRUE(count <= TEST_MAX_EVENTS);

    g_calls[g_call_count].requested = count;
    memcpy(g_calls[g_call_count].events, events, count * sizeof(INPUT));
    accepted = g_configured_accepts[g_call_count];
    if (accepted == FAKE_ACCEPT_ALL) {
        accepted = count;
    }
    ASSERT_TRUE(accepted <= count);
    g_calls[g_call_count].accepted = accepted;
    g_call_count += 1;
    return accepted;
}

static VOID WINAPI fake_sleep(DWORD milliseconds)
{
    g_sleep_ms = milliseconds;
}

static InputHelperHooks fake_hooks(void)
{
    InputHelperHooks hooks;
    hooks.send_input = fake_send_input;
    hooks.sleep_ms = fake_sleep;
    return hooks;
}

static void assert_key_event(const INPUT *event, WORD key, DWORD flags)
{
    ASSERT_EQ_UINT(INPUT_KEYBOARD, event->type);
    ASSERT_EQ_UINT(key, event->ki.wVk);
    ASSERT_EQ_UINT(0, event->ki.wScan);
    ASSERT_EQ_UINT(flags, event->ki.dwFlags);
}

static int run_valid_command(char *output, size_t output_size)
{
    char *arguments[] = {
        "TrainerRelay.InputHelper.exe",
        "--protocol",
        "1",
        "--key",
        "112",
        "--modifiers",
        "3",
        "--hold-ms",
        "40",
    };
    InputHelperHooks hooks = fake_hooks();

    return input_helper_run((int)(sizeof(arguments) / sizeof(arguments[0])), arguments, &hooks, output, output_size);
}

static void test_ctrl_alt_f1_order_and_bounded_json(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_OK, (UINT)result);
    ASSERT_EQ_UINT(2, g_call_count);
    ASSERT_EQ_UINT(40, g_sleep_ms);
    ASSERT_EQ_UINT(3, g_calls[0].requested);
    ASSERT_EQ_UINT(3, g_calls[0].accepted);
    assert_key_event(&g_calls[0].events[0], VK_CONTROL, 0);
    assert_key_event(&g_calls[0].events[1], VK_MENU, 0);
    assert_key_event(&g_calls[0].events[2], 0x70, 0);
    ASSERT_EQ_UINT(3, g_calls[1].requested);
    ASSERT_EQ_UINT(3, g_calls[1].accepted);
    assert_key_event(&g_calls[1].events[0], 0x70, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[1].events[1], VK_MENU, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[1].events[2], VK_CONTROL, KEYEVENTF_KEYUP);
    ASSERT_TRUE(strlen(output) < INPUT_HELPER_MAX_JSON_LINE_BYTES);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":6,\"expected_count\":6,\"result_code\":0}") == 0);
}

static void test_partial_press_sends_reverse_cleanup_without_sleep(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    g_configured_accepts[0] = 2;
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_SEND_FAILED, (UINT)result);
    ASSERT_EQ_UINT(2, g_call_count);
    ASSERT_EQ_UINT(0, g_sleep_ms);
    ASSERT_EQ_UINT(3, g_calls[0].requested);
    ASSERT_EQ_UINT(2, g_calls[0].accepted);
    ASSERT_EQ_UINT(2, g_calls[1].requested);
    ASSERT_EQ_UINT(2, g_calls[1].accepted);
    assert_key_event(&g_calls[1].events[0], VK_MENU, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[1].events[1], VK_CONTROL, KEYEVENTF_KEYUP);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":4,\"expected_count\":6,\"result_code\":3}") == 0);
}

static void test_partial_release_sends_remaining_cleanup(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    g_configured_accepts[1] = 1;
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_SEND_FAILED, (UINT)result);
    ASSERT_EQ_UINT(3, g_call_count);
    ASSERT_EQ_UINT(2, g_calls[2].requested);
    ASSERT_EQ_UINT(2, g_calls[2].accepted);
    assert_key_event(&g_calls[2].events[0], VK_MENU, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[2].events[1], VK_CONTROL, KEYEVENTF_KEYUP);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":6,\"expected_count\":6,\"result_code\":3}") == 0);
}

static void test_zero_press_stops_without_sleep_or_cleanup(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    g_configured_accepts[0] = 0;
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_SEND_FAILED, (UINT)result);
    ASSERT_EQ_UINT(1, g_call_count);
    ASSERT_EQ_UINT(0, g_sleep_ms);
    ASSERT_EQ_UINT(3, g_calls[0].requested);
    ASSERT_EQ_UINT(0, g_calls[0].accepted);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":0,\"expected_count\":6,\"result_code\":3}") == 0);
}

static void test_zero_release_retries_full_reverse_cleanup(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    g_configured_accepts[1] = 0;
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_SEND_FAILED, (UINT)result);
    ASSERT_EQ_UINT(3, g_call_count);
    ASSERT_EQ_UINT(40, g_sleep_ms);
    ASSERT_EQ_UINT(3, g_calls[1].requested);
    ASSERT_EQ_UINT(0, g_calls[1].accepted);
    ASSERT_EQ_UINT(3, g_calls[2].requested);
    ASSERT_EQ_UINT(3, g_calls[2].accepted);
    assert_key_event(&g_calls[2].events[0], 0x70, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[2].events[1], VK_MENU, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[2].events[2], VK_CONTROL, KEYEVENTF_KEYUP);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":6,\"expected_count\":6,\"result_code\":3}") == 0);
}

static void test_zero_cleanup_stops_after_one_reverse_attempt(void)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    int result;

    reset_fake();
    g_configured_accepts[0] = 2;
    g_configured_accepts[1] = 0;
    result = run_valid_command(output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_SEND_FAILED, (UINT)result);
    ASSERT_EQ_UINT(2, g_call_count);
    ASSERT_EQ_UINT(0, g_sleep_ms);
    ASSERT_EQ_UINT(2, g_calls[1].requested);
    ASSERT_EQ_UINT(0, g_calls[1].accepted);
    assert_key_event(&g_calls[1].events[0], VK_MENU, KEYEVENTF_KEYUP);
    assert_key_event(&g_calls[1].events[1], VK_CONTROL, KEYEVENTF_KEYUP);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":2,\"expected_count\":6,\"result_code\":3}") == 0);
}

static void test_invalid_allowlisted_key_makes_no_input_calls(void)
{
    char *arguments[] = {
        "TrainerRelay.InputHelper.exe",
        "--protocol",
        "1",
        "--key",
        "27",
        "--modifiers",
        "0",
        "--hold-ms",
        "40",
    };
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    InputHelperHooks hooks = fake_hooks();
    int result;

    reset_fake();
    result = input_helper_run((int)(sizeof(arguments) / sizeof(arguments[0])), arguments, &hooks, output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_INVALID_ARGUMENT, (UINT)result);
    ASSERT_EQ_UINT(0, g_call_count);
    ASSERT_EQ_UINT(0, g_sleep_ms);
    ASSERT_TRUE(strcmp(output, "{\"protocol\":1,\"accepted_count\":0,\"expected_count\":0,\"result_code\":2}") == 0);
}

static void test_malformed_argument_makes_no_input_calls(void)
{
    char *arguments[] = {
        "TrainerRelay.InputHelper.exe",
        "--protocol",
        "1x",
        "--key",
        "112",
        "--modifiers",
        "0",
        "--hold-ms",
        "40",
    };
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    InputHelperHooks hooks = fake_hooks();
    int result;

    reset_fake();
    result = input_helper_run((int)(sizeof(arguments) / sizeof(arguments[0])), arguments, &hooks, output, sizeof(output));

    ASSERT_EQ_UINT(INPUT_HELPER_RESULT_INVALID_ARGUMENT, (UINT)result);
    ASSERT_EQ_UINT(0, g_call_count);
    ASSERT_TRUE(strstr(output, "\"result_code\":2") != NULL);
}

int main(void)
{
    test_ctrl_alt_f1_order_and_bounded_json();
    test_partial_press_sends_reverse_cleanup_without_sleep();
    test_partial_release_sends_remaining_cleanup();
    test_zero_press_stops_without_sleep_or_cleanup();
    test_zero_release_retries_full_reverse_cleanup();
    test_zero_cleanup_stops_after_one_reverse_attempt();
    test_invalid_allowlisted_key_makes_no_input_calls();
    test_malformed_argument_makes_no_input_calls();
    puts("input_helper_test: PASS");
    return 0;
}
