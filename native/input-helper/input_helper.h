#ifndef TRAINER_RELAY_INPUT_HELPER_H
#define TRAINER_RELAY_INPUT_HELPER_H

#include <windows.h>

#include <stddef.h>

#define INPUT_HELPER_PROTOCOL_VERSION 1
#define INPUT_HELPER_MAX_JSON_LINE_BYTES 256

enum InputHelperResultCode {
    INPUT_HELPER_RESULT_OK = 0,
    INPUT_HELPER_RESULT_INTERNAL_ERROR = 1,
    INPUT_HELPER_RESULT_INVALID_ARGUMENT = 2,
    INPUT_HELPER_RESULT_SEND_FAILED = 3,
};

typedef UINT(WINAPI *InputHelperSendInput)(UINT count, LPINPUT events, int size);
typedef VOID(WINAPI *InputHelperSleep)(DWORD milliseconds);

typedef struct InputHelperHooks {
    InputHelperSendInput send_input;
    InputHelperSleep sleep_ms;
} InputHelperHooks;

int input_helper_run(
    int argc,
    char **argv,
    const InputHelperHooks *hooks,
    char *output,
    size_t output_size);

#endif
