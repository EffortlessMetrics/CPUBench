#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <time.h>
#endif

#define PROVIDER_ID "native-c11"
#define PROVIDER_VERSION "0.2.0"

static const char *timer_name(void) {
#ifdef _WIN32
    return "QueryPerformanceCounter";
#else
#ifdef CLOCK_MONOTONIC_RAW
    return "CLOCK_MONOTONIC_RAW";
#else
    return "CLOCK_MONOTONIC";
#endif
#endif
}

static uint64_t now_ns(void) {
#ifdef _WIN32
    LARGE_INTEGER counter;
    LARGE_INTEGER frequency;
    if (!QueryPerformanceCounter(&counter) || !QueryPerformanceFrequency(&frequency)) {
        return 0;
    }
    return (uint64_t)(((long double)counter.QuadPart * 1000000000.0L) / (long double)frequency.QuadPart);
#else
    struct timespec ts;
#ifdef CLOCK_MONOTONIC_RAW
    const clockid_t clock_id = CLOCK_MONOTONIC_RAW;
#else
    const clockid_t clock_id = CLOCK_MONOTONIC;
#endif
    if (clock_gettime(clock_id, &ts) != 0) {
        return 0;
    }
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

static uint64_t rng_next(uint64_t *state) {
    uint64_t x = *state;
    if (x == 0) {
        x = 0x9E3779B97F4A7C15ULL;
    }
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

static int parse_u64(const char *text, uint64_t *out) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        return -1;
    }
    *out = (uint64_t)value;
    return 0;
}

static const char *arg_value(int argc, char **argv, const char *name) {
    for (int i = 2; i + 1 < argc; ++i) {
        if (strcmp(argv[i], name) == 0) {
            return argv[i + 1];
        }
    }
    return NULL;
}

static void shuffle(uint32_t *values, size_t count, uint64_t *seed) {
    if (count < 2) {
        return;
    }
    for (size_t i = count - 1; i > 0; --i) {
        size_t j = (size_t)(rng_next(seed) % (i + 1));
        uint32_t temp = values[i];
        values[i] = values[j];
        values[j] = temp;
    }
}

static int build_cycles(uint32_t *next, size_t count, unsigned chains, uint64_t seed, uint32_t *starts) {
    if (count < (size_t)chains * 2U || chains == 0U || chains > 16U) {
        return -1;
    }
    uint32_t *permutation = (uint32_t *)malloc(count * sizeof(uint32_t));
    if (permutation == NULL) {
        return -1;
    }
    for (size_t i = 0; i < count; ++i) {
        permutation[i] = (uint32_t)i;
    }
    shuffle(permutation, count, &seed);

    for (unsigned chain = 0; chain < chains; ++chain) {
        size_t first = chain;
        size_t previous = first;
        starts[chain] = permutation[first];
        for (size_t position = first + chains; position < count; position += chains) {
            next[permutation[previous]] = permutation[position];
            previous = position;
        }
        next[permutation[previous]] = permutation[first];
    }

    free(permutation);
    return 0;
}

static int verify_cycles(const uint32_t *next, size_t count, unsigned chains, const uint32_t *starts) {
    unsigned char *seen = (unsigned char *)calloc(count, 1);
    if (seen == NULL) {
        return -1;
    }
    size_t visited = 0;
    for (unsigned chain = 0; chain < chains; ++chain) {
        uint32_t current = starts[chain];
        while (!seen[current]) {
            seen[current] = 1;
            ++visited;
            current = next[current];
            if (current >= count) {
                free(seen);
                return -1;
            }
        }
        if (current != starts[chain]) {
            free(seen);
            return -1;
        }
    }
    free(seen);
    return visited == count ? 0 : -1;
}

static uint64_t chase1(const uint32_t *next, uint32_t *starts, uint64_t total_units) {
    uint32_t a = starts[0];
    for (uint64_t i = 0; i < total_units; ++i) {
        a = next[a];
    }
    starts[0] = a;
    return a;
}

static uint64_t chase2(const uint32_t *next, uint32_t *s, uint64_t rounds) {
    uint32_t a = s[0], b = s[1];
    for (uint64_t i = 0; i < rounds; ++i) { a = next[a]; b = next[b]; }
    s[0] = a; s[1] = b;
    return (uint64_t)a ^ ((uint64_t)b << 32);
}

static uint64_t chase4(const uint32_t *next, uint32_t *s, uint64_t rounds) {
    uint32_t a=s[0], b=s[1], c=s[2], d=s[3];
    for (uint64_t i=0; i<rounds; ++i) { a=next[a]; b=next[b]; c=next[c]; d=next[d]; }
    s[0]=a; s[1]=b; s[2]=c; s[3]=d;
    return (uint64_t)a ^ ((uint64_t)b<<16) ^ ((uint64_t)c<<32) ^ ((uint64_t)d<<48);
}

static uint64_t chase8(const uint32_t *next, uint32_t *s, uint64_t rounds) {
    uint32_t a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
    for (uint64_t i=0; i<rounds; ++i) {
        a=next[a]; b=next[b]; c=next[c]; d=next[d];
        e=next[e]; f=next[f]; g=next[g]; h=next[h];
    }
    s[0]=a;s[1]=b;s[2]=c;s[3]=d;s[4]=e;s[5]=f;s[6]=g;s[7]=h;
    return (uint64_t)a ^ ((uint64_t)b<<8) ^ ((uint64_t)c<<16) ^ ((uint64_t)d<<24) ^
           ((uint64_t)e<<32) ^ ((uint64_t)f<<40) ^ ((uint64_t)g<<48) ^ ((uint64_t)h<<56);
}

static uint64_t chase16(const uint32_t *next, uint32_t *s, uint64_t rounds) {
    uint32_t a0=s[0],a1=s[1],a2=s[2],a3=s[3],a4=s[4],a5=s[5],a6=s[6],a7=s[7];
    uint32_t a8=s[8],a9=s[9],a10=s[10],a11=s[11],a12=s[12],a13=s[13],a14=s[14],a15=s[15];
    for (uint64_t i=0; i<rounds; ++i) {
        a0=next[a0];a1=next[a1];a2=next[a2];a3=next[a3];
        a4=next[a4];a5=next[a5];a6=next[a6];a7=next[a7];
        a8=next[a8];a9=next[a9];a10=next[a10];a11=next[a11];
        a12=next[a12];a13=next[a13];a14=next[a14];a15=next[a15];
    }
    uint32_t values[16]={a0,a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11,a12,a13,a14,a15};
    uint64_t checksum=0;
    for (unsigned i=0;i<16;++i) { s[i]=values[i]; checksum ^= ((uint64_t)values[i]) << ((i%8)*8); }
    return checksum;
}

static uint64_t run_chase(const uint32_t *next, uint32_t *starts, unsigned chains, uint64_t requested_units, uint64_t *actual_units) {
    if (chains == 1U) {
        *actual_units = requested_units;
        return chase1(next, starts, requested_units);
    }
    uint64_t rounds = requested_units / chains;
    if (rounds == 0) {
        rounds = 1;
    }
    *actual_units = rounds * chains;
    switch (chains) {
        case 2U: return chase2(next, starts, rounds);
        case 4U: return chase4(next, starts, rounds);
        case 8U: return chase8(next, starts, rounds);
        case 16U: return chase16(next, starts, rounds);
        default: return 0;
    }
}

static int run_timer_overhead(int argc, char **argv) {
    const char *units_text = arg_value(argc, argv, "--completed-units");
    const char *samples_text = arg_value(argc, argv, "--samples");
    const char *warmup_text = arg_value(argc, argv, "--warmup-samples");
    uint64_t completed_units = 0, samples = 0, warmups = 0;

    if (units_text == NULL || samples_text == NULL ||
        parse_u64(units_text, &completed_units) != 0 ||
        parse_u64(samples_text, &samples) != 0 ||
        (warmup_text != NULL && parse_u64(warmup_text, &warmups) != 0) ||
        completed_units == 0 || samples == 0) {
        fprintf(stderr, "invalid native timer-control dimensions\n");
        return 2;
    }

    printf("{\"record_type\":\"metadata\",\"family_id\":\"controls.native_timer_overhead\",\"timer\":\"%s\",\"timer_control\":true,\"setup_excluded\":true}\n", timer_name());
    uint64_t previous_reading = 0;
    uint64_t carried_non_monotonic_count = 0;
    for (uint64_t sample = 0; sample < warmups + samples; ++sample) {
        uint64_t checksum = 0;
        uint64_t non_monotonic_count = carried_non_monotonic_count;
        carried_non_monotonic_count = 0;
        uint64_t zero_delta_count = 0;
        uint64_t min_positive_delta_ns = UINT64_MAX;
        uint64_t max_delta_ns = 0;
        uint64_t sum_pair_delta_ns = 0;
        uint64_t outer_start = now_ns();
        if (outer_start == 0) {
            fprintf(stderr, "timer failure\n");
            return 3;
        }
        if (previous_reading != 0 && outer_start < previous_reading) {
            ++non_monotonic_count;
        }
        previous_reading = outer_start;
        for (uint64_t i = 0; i < completed_units; ++i) {
            uint64_t a = now_ns();
            if (a == 0) {
                fprintf(stderr, "timer failure\n");
                return 3;
            }
            if (a < previous_reading) {
                ++non_monotonic_count;
            }
            previous_reading = a;

            uint64_t b = now_ns();
            if (b == 0) {
                fprintf(stderr, "timer failure\n");
                return 3;
            }
            uint64_t delta = 0;
            if (b < previous_reading) {
                ++non_monotonic_count;
            } else {
                delta = b - a;
            }
            previous_reading = b;
            if (delta == 0) {
                ++zero_delta_count;
            } else {
                if (delta < min_positive_delta_ns) {
                    min_positive_delta_ns = delta;
                }
                if (delta > max_delta_ns) {
                    max_delta_ns = delta;
                }
            }
            sum_pair_delta_ns += delta;
            checksum ^= delta;
        }
        uint64_t outer_end = now_ns();
        if (outer_end == 0) {
            fprintf(stderr, "timer failure\n");
            return 3;
        }
        if (outer_end < previous_reading) {
            ++non_monotonic_count;
        }
        previous_reading = outer_end;
        if (outer_end < outer_start) {
            fprintf(stderr, "timer failure: outer interval reversed\n");
            return 3;
        }
        if (sample < warmups) {
            carried_non_monotonic_count += non_monotonic_count;
            continue;
        }
        uint64_t elapsed = outer_end - outer_start;
        if (elapsed == 0) {
            elapsed = 1;
        }
        uint64_t effective_resolution = min_positive_delta_ns == UINT64_MAX ? 0 : min_positive_delta_ns;
        printf("{\"record_type\":\"sample\",\"sample_index\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64 ",\"completed_units\":%" PRIu64 ",\"checksum\":\"timer:%016" PRIx64 ":%" PRIu64 ":%" PRIu64 "\",\"timer\":\"%s\",\"non_monotonic_count\":%" PRIu64 ",\"zero_delta_count\":%" PRIu64 ",\"min_positive_delta_ns\":%" PRIu64 ",\"max_delta_ns\":%" PRIu64 ",\"sum_pair_delta_ns\":%" PRIu64 "}\n",
               sample - warmups, elapsed, completed_units, checksum,
               non_monotonic_count, zero_delta_count, timer_name(),
               non_monotonic_count, zero_delta_count, effective_resolution,
               max_delta_ns, sum_pair_delta_ns);
    }
    return 0;
}

static int describe(void) {
    printf("{\"artifact_kind\":\"provider_descriptor\",\"schema_version\":1,\"provider_id\":\"%s\",\"provider_version\":\"%s\",\"protocol_version\":1,\"families\":[", PROVIDER_ID, PROVIDER_VERSION);
    printf("{\"family_id\":\"controls.native_timer_overhead\",\"implementation_id\":\"native-c11-v1\",\"supported_os\":[\"linux\",\"windows\",\"darwin\"],\"supported_arch\":[\"x86_64\",\"amd64\",\"aarch64\",\"arm64\"],\"timing_authority\":\"provider_elapsed\",\"capabilities\":[]},");
    printf("{\"family_id\":\"memory.dependent_load_latency\",\"implementation_id\":\"native-c11-v1\",\"supported_os\":[\"linux\",\"windows\",\"darwin\"],\"supported_arch\":[\"x86_64\",\"amd64\",\"aarch64\",\"arm64\"],\"timing_authority\":\"provider_elapsed\",\"capabilities\":[]},");
    printf("{\"family_id\":\"memory.memory_level_parallelism\",\"implementation_id\":\"native-c11-v1\",\"supported_os\":[\"linux\",\"windows\",\"darwin\"],\"supported_arch\":[\"x86_64\",\"amd64\",\"aarch64\",\"arm64\"],\"timing_authority\":\"provider_elapsed\",\"capabilities\":[]}");
    printf("]}\n");
    return 0;
}

static int self_test(void) {
    const size_t count = 4096;
    uint32_t *next = (uint32_t *)malloc(count * sizeof(uint32_t));
    uint32_t starts[16] = {0};
    if (next == NULL || build_cycles(next, count, 4, 7, starts) != 0 || verify_cycles(next, count, 4, starts) != 0) {
        free(next);
        printf("{\"ok\":false,\"reason\":\"cycle_validation_failed\"}\n");
        return 1;
    }
    uint64_t units = 0;
    uint64_t checksum = run_chase(next, starts, 4, 10000, &units);
    free(next);
    printf("{\"ok\":true,\"timer\":\"%s\",\"completed_units\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\"}\n", timer_name(), units, checksum);
    return 0;
}

static int run_benchmark(int argc, char **argv) {
    const char *family = arg_value(argc, argv, "--family");
    if (family == NULL) {
        fprintf(stderr, "missing required family argument\n");
        return 2;
    }
    if (strcmp(family, "controls.native_timer_overhead") == 0) {
        return run_timer_overhead(argc, argv);
    }

    const char *working_text = arg_value(argc, argv, "--working-set-bytes");
    const char *chains_text = arg_value(argc, argv, "--chains");
    const char *units_text = arg_value(argc, argv, "--completed-units");
    const char *samples_text = arg_value(argc, argv, "--samples");
    const char *warmup_text = arg_value(argc, argv, "--warmup-samples");
    const char *seed_text = arg_value(argc, argv, "--seed");

    if (working_text == NULL || units_text == NULL || samples_text == NULL) {
        fprintf(stderr, "missing required run arguments\n");
        return 2;
    }
    if (strcmp(family, "memory.dependent_load_latency") != 0 && strcmp(family, "memory.memory_level_parallelism") != 0) {
        fprintf(stderr, "unsupported family: %s\n", family);
        return 64;
    }

    uint64_t working_set_bytes=0, requested_units=0, samples=0, warmups=0, seed=1, chains_u64=1;
    if (parse_u64(working_text, &working_set_bytes) != 0 ||
        parse_u64(units_text, &requested_units) != 0 ||
        parse_u64(samples_text, &samples) != 0 ||
        (warmup_text != NULL && parse_u64(warmup_text, &warmups) != 0) ||
        (seed_text != NULL && parse_u64(seed_text, &seed) != 0) ||
        (chains_text != NULL && parse_u64(chains_text, &chains_u64) != 0)) {
        fprintf(stderr, "invalid numeric argument\n");
        return 2;
    }

    unsigned chains = (unsigned)chains_u64;
    if (strcmp(family, "memory.dependent_load_latency") == 0) {
        chains = 1U;
    }
    if (!(chains == 1U || chains == 2U || chains == 4U || chains == 8U || chains == 16U)) {
        fprintf(stderr, "unsupported chain count: %u\n", chains);
        return 64;
    }
    if (samples == 0 || requested_units == 0 || working_set_bytes < sizeof(uint32_t) * chains * 2U) {
        fprintf(stderr, "invalid benchmark dimensions\n");
        return 2;
    }

    size_t count = (size_t)(working_set_bytes / sizeof(uint32_t));
    if (count > UINT32_MAX) {
        fprintf(stderr, "working set too large for index representation\n");
        return 64;
    }
    uint32_t *next = (uint32_t *)malloc(count * sizeof(uint32_t));
    uint32_t starts[16] = {0};
    if (next == NULL) {
        fprintf(stderr, "allocation failed for %zu entries\n", count);
        return 3;
    }
    if (build_cycles(next, count, chains, seed, starts) != 0 || verify_cycles(next, count, chains, starts) != 0) {
        free(next);
        fprintf(stderr, "cycle generation or validation failed\n");
        return 3;
    }

    printf("{\"record_type\":\"metadata\",\"family_id\":\"%s\",\"working_set_bytes\":%zu,\"chains\":%u,\"seed\":%" PRIu64 ",\"timer\":\"%s\",\"cycle_validated\":true,\"disjoint_chains\":true,\"setup_excluded\":true}\n", family, count * sizeof(uint32_t), chains, seed, timer_name());

    uint64_t combined_checksum = 0;
    for (uint64_t sample = 0; sample < warmups + samples; ++sample) {
        uint32_t local_starts[16] = {0};
        for (unsigned i = 0; i < chains; ++i) {
            local_starts[i] = starts[i];
        }
        uint64_t actual_units = 0;
        uint64_t start = now_ns();
        uint64_t checksum = run_chase(next, local_starts, chains, requested_units, &actual_units);
        uint64_t end = now_ns();
        if (start == 0 || end < start) {
            free(next);
            fprintf(stderr, "timer failure\n");
            return 3;
        }
        combined_checksum ^= checksum;
        if (sample < warmups) {
            continue;
        }
        uint64_t elapsed = end - start;
        if (elapsed == 0) {
            elapsed = 1;
        }
        printf("{\"record_type\":\"sample\",\"sample_index\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64 ",\"completed_units\":%" PRIu64 ",\"checksum\":\"%016" PRIx64 "\",\"timer\":\"%s\",\"working_set_bytes\":%zu,\"chains\":%u}\n", sample - warmups, elapsed, actual_units, checksum, timer_name(), count * sizeof(uint32_t), chains);
    }

    if (combined_checksum == UINT64_MAX) {
        fprintf(stderr, "checksum sentinel: %" PRIu64 "\n", combined_checksum);
    }
    free(next);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: cpubench-native <describe|self-test|run>\n");
        return 2;
    }
    if (strcmp(argv[1], "describe") == 0) {
        return describe();
    }
    if (strcmp(argv[1], "self-test") == 0) {
        return self_test();
    }
    if (strcmp(argv[1], "run") == 0) {
        return run_benchmark(argc, argv);
    }
    fprintf(stderr, "unknown command: %s\n", argv[1]);
    return 2;
}
