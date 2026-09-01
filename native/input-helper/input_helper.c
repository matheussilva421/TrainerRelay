#include "input_helper.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "user32.lib")

#define INPUT_HELPER_ARGUMENT_COUNT 9
#define INPUT_HELPER_MAX_MODIFIERS 3
#define INPUT_HELPER_MIN_HOLD_MS 1
#define INPUT_HELPER_MAX_HOLD_MS 1000
#define INPUT_HELPER_ALLOWED_MODIFIERS 7UL

static UINT WINAPI native_send_input(UINT count, LPINPUT events, int size)
{
    return SendInput(count, events, size);
}

static VOID WINAPI native_sleep(DWORD milliseconds)
{
    Sleep(milliseconds);
}

static int parse_unsigned(const char *text, unsigned long *value)
{
    char *end;
    const unsigned char *cursor;
    unsigned long parsed;

    if (text == NULL || *text == '\0' || *text == '-' || *text == '+') {
        return 0;
    }
    cursor = (const unsigned char *)text;
    while (*cursor != '\0') {
        if (*cursor < '0' || *cursor > '9') {
            return 0;
        }
        cursor += 1;
    }
    errno = 0;
    end = NULL;
    parsed = strtoul(text, &end, 10);
    if (errno == ERANGE || end == text || *end != '\0') {
        return 0;
    }
    *value = parsed;
    return 1;
}

static int is_allowed_virtual_key(unsigned long key)
{
    if ((key >= 'A' && key <= 'Z') ||
        (key >= '0' && key <= '9') ||
        (key >= VK_F1 && key <= VK_F24) ||
        (key >= VK_NUMPAD0 && key <= VK_NUMPAD9)) {
        return 1;
    }

    switch (key) {
    case VK_MULTIPLY:
    case VK_ADD:
    case VK_SUBTRACT:
    case VK_DECIMAL:
    case VK_DIVIDE:
    case VK_INSERT:
    case VK_DELETE:
    case VK_HOME:
    case VK_END:
    case VK_PRIOR:
    case VK_NEXT:
    case VK_UP:
    case VK_DOWN:
    case VK_LEFT:
    case VK_RIGHT:
    case VK_SPACE:
    case VK_TAB:
    case VK_RETURN:
    case VK_BACK:
    case VK_PAUSE:
    case VK_CAPITAL:
    case VK_SCROLL:
    case VK_NUMLOCK:
        return 1;
    default:
        return 0;
    }
}

static int append_key_event(INPUT *events, size_t *count, WORD virtual_key, DWORD flags)
{
    if (*count >= INPUT_HELPER_MAX_MODIFIERS + 1) {
        return 0;
    }
    memset(&events[*count], 0, sizeof(events[*count]));
    events[*count].type = INPUT_KEYBOARD;
    events[*count].ki.wVk = virtual_key;
    events[*count].ki.dwFlags = flags;
    *count += 1;
    return 1;
}

static size_t build_press_events(unsigned long key, unsigned long modifiers, INPUT *events)
{
    size_t count = 0;

    if ((modifiers & 1UL) != 0 && !append_key_event(events, &count, VK_CONTROL, 0)) {
        return 0;
    }
    if ((modifiers & 2UL) != 0 && !append_key_event(events, &count, VK_MENU, 0)) {
        return 0;
    }
    if ((modifiers & 4UL) != 0 && !append_key_event(events, &count, VK_SHIFT, 0)) {
        return 0;
    }
    if (!append_key_event(events, &count, (WORD)key, 0)) {
        return 0;
    }
    return count;
}

static size_t build_release_events(const INPUT *press_events, size_t press_count, INPUT *release_events)
{
    size_t index;
    size_t count = 0;

    for (index = press_count; index > 0; --index) {
        release_events[count] = press_events[index - 1];
        release_events[count].ki.dwFlags |= KEYEVENTF_KEYUP;
        count += 1;
    }
    return count;
}

static UINT best_effort_release(
    const InputHelperHooks *hooks,
    const INPUT *release_events,
    size_t first_unreleased,
    size_t release_count)
{
    if (first_unreleased < release_count) {
        return hooks->send_input(
            (UINT)(release_count - first_unreleased),
            (LPINPUT)&release_events[first_unreleased],
            (int)sizeof(INPUT));
    }
    return 0;
}

static int write_result(
    char *output,
    size_t output_size,
    unsigned long accepted_count,
    unsigned long expected_count,
    int result_code)
{
    int written;

    if (output == NULL || output_size == 0) {
        return INPUT_HELPER_RESULT_INTERNAL_ERROR;
    }
    written = _snprintf_s(
        output,
        output_size,
        _TRUNCATE,
        "{\"protocol\":%d,\"accepted_count\":%lu,\"expected_count\":%lu,\"result_code\":%d}",
        INPUT_HELPER_PROTOCOL_VERSION,
        accepted_count,
        expected_count,
        result_code);
    if (written < 0 || (size_t)written >= output_size) {
        output[0] = '\0';
        return INPUT_HELPER_RESULT_INTERNAL_ERROR;
    }
    return result_code;
}

int input_helper_run(
    int argc,
    char **argv,
    const InputHelperHooks *hooks,
    char *output,
    size_t output_size)
{
    InputHelperHooks native_hooks;
    INPUT press_events[INPUT_HELPER_MAX_MODIFIERS + 1];
    INPUT release_events[INPUT_HELPER_MAX_MODIFIERS + 1];
    unsigned long protocol;
    unsigned long key;
    unsigned long modifiers;
    unsigned long hold_ms;
    unsigned long accepted_count = 0;
    size_t press_count;
    size_t release_count;
    UINT accepted;
    UINT cleanup_accepted;
    int result_code = INPUT_HELPER_RESULT_OK;

    if (argc != INPUT_HELPER_ARGUMENT_COUNT || argv == NULL) {
        return write_result(output, output_size, 0, 0, INPUT_HELPER_RESULT_INVALID_ARGUMENT);
    }

    if (argv[1] == NULL || argv[2] == NULL || argv[3] == NULL || argv[4] == NULL ||
        argv[5] == NULL || argv[6] == NULL || argv[7] == NULL || argv[8] == NULL ||
        strcmp(argv[1], "--protocol") != 0 ||
        strcmp(argv[3], "--key") != 0 ||
        strcmp(argv[5], "--modifiers") != 0 ||
        strcmp(argv[7], "--hold-ms") != 0 ||
        !parse_unsigned(argv[2], &protocol) ||
        !parse_unsigned(argv[4], &key) ||
        !parse_unsigned(argv[6], &modifiers) ||
        !parse_unsigned(argv[8], &hold_ms) ||
        protocol != INPUT_HELPER_PROTOCOL_VERSION ||
        key > 0xFFFFUL ||
        !is_allowed_virtual_key(key) ||
        modifiers > INPUT_HELPER_ALLOWED_MODIFIERS ||
        hold_ms < INPUT_HELPER_MIN_HOLD_MS ||
        hold_ms > INPUT_HELPER_MAX_HOLD_MS) {
        return write_result(output, output_size, 0, 0, INPUT_HELPER_RESULT_INVALID_ARGUMENT);
    }

    if (hooks == NULL || hooks->send_input == NULL || hooks->sleep_ms == NULL) {
        return write_result(output, output_size, 0, 0, INPUT_HELPER_RESULT_INTERNAL_ERROR);
    }
    native_hooks = *hooks;

    press_count = build_press_events(key, modifiers, press_events);
    release_count = build_release_events(press_events, press_count, release_events);
    if (press_count == 0 || release_count == 0 || release_count != press_count) {
        return write_result(output, output_size, 0, 0, INPUT_HELPER_RESULT_INTERNAL_ERROR);
    }

    accepted = native_hooks.send_input((UINT)press_count, press_events, (int)sizeof(INPUT));
    if (accepted > press_count) {
        accepted = 0;
        result_code = INPUT_HELPER_RESULT_SEND_FAILED;
    }
    accepted_count = accepted;
    if (accepted != press_count) {
        cleanup_accepted = best_effort_release(&native_hooks, release_events, press_count - accepted, release_count);
        if (cleanup_accepted <= release_count - (press_count - accepted)) {
            accepted_count += cleanup_accepted;
        }
        return write_result(output, output_size, accepted_count, (unsigned long)(press_count + release_count), result_code == INPUT_HELPER_RESULT_OK ? INPUT_HELPER_RESULT_SEND_FAILED : result_code);
    }

    native_hooks.sleep_ms((DWORD)hold_ms);
    accepted = native_hooks.send_input((UINT)release_count, release_events, (int)sizeof(INPUT));
    if (accepted > release_count) {
        accepted = 0;
        result_code = INPUT_HELPER_RESULT_SEND_FAILED;
    }
    accepted_count += accepted;
    if (accepted != release_count) {
        cleanup_accepted = best_effort_release(&native_hooks, release_events, accepted, release_count);
        if (cleanup_accepted <= release_count - accepted) {
            accepted_count += cleanup_accepted;
        }
        return write_result(output, output_size, accepted_count, (unsigned long)(press_count + release_count), result_code == INPUT_HELPER_RESULT_OK ? INPUT_HELPER_RESULT_SEND_FAILED : result_code);
    }

    return write_result(output, output_size, accepted_count, (unsigned long)(press_count + release_count), INPUT_HELPER_RESULT_OK);
}

#ifndef INPUT_HELPER_TEST
int main(int argc, char **argv)
{
    char output[INPUT_HELPER_MAX_JSON_LINE_BYTES];
    InputHelperHooks hooks;
    int result;

    hooks.send_input = native_send_input;
    hooks.sleep_ms = native_sleep;
    result = input_helper_run(argc, argv, &hooks, output, sizeof(output));
    if (output[0] != '\0') {
        fputs(output, stdout);
        fputc('\n', stdout);
    }
    return result;
}
#endif
