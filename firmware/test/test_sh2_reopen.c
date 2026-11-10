/* Host regression test against the actual SH2/SHTP dependency. */
#include <stdio.h>
#include "sh2.h"
static int opens, closes;
static int hal_open(sh2_Hal_t *s) { opens++; return 0; }
static void hal_close(sh2_Hal_t *s) { closes++; }
static int hal_read(sh2_Hal_t *s, uint8_t *p, unsigned n, uint32_t *t) { return 0; }
static int hal_write(sh2_Hal_t *s, uint8_t *p, unsigned n) { return n; }
static uint32_t hal_time(sh2_Hal_t *s) { static uint32_t now; return now += 100000; }
int main(void) {
    sh2_Hal_t hal = {hal_open, hal_close, hal_read, hal_write, hal_time};
    for (int i = 0; i < 100; i++) {
        int result = sh2_open(&hal, NULL, NULL);
        if (result != 0) { printf("FAIL: reopen %d returned %d\n", i + 1, result); return 1; }
    }
    sh2_close();
    if (opens != 100 || closes != 100) return 2;
    puts("PASS: 100 SH2 reopen cycles, all sessions released");
    return 0;
}
