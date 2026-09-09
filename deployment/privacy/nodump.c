/* Applied by the ELF loader to each dynamic service/worker executable.
 * RLIMIT_CORE alone is ignored by piped WSL core handlers. Fail closed. */
#include <sys/prctl.h>
#include <sys/resource.h>
#include <unistd.h>
__attribute__((constructor)) static void disable_core_dumps(void) {
    struct rlimit limit = {0, 0};
    if (setrlimit(RLIMIT_CORE, &limit) || prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)) {
        static const char message[] = "EphemerAI: cannot enforce core-dump policy\n";
        ssize_t ignored = write(2, message, sizeof(message)-1);
        (void)ignored;
        _exit(125);
    }
}
