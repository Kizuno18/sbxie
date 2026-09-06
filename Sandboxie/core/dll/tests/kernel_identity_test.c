// SPDX-License-Identifier: GPL-3.0-or-later
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>

#define CHECK(condition) do { if (!(condition)) { \
	fprintf(stderr, "FAIL at line %d: %s\n", __LINE__, #condition); exit(1); \
} } while (0)

#ifdef _MSC_VER
#define THREAD_LOCAL __declspec(thread)
#else
#define THREAD_LOCAL _Thread_local
#endif
#ifdef _WIN32
#include <windows.h>
typedef LONG NTSTATUS;
#else
#include <pthread.h>
#include <strings.h>
typedef uint32_t DWORD;
typedef uintptr_t UINT_PTR;
typedef uint32_t ULONG;
typedef int32_t NTSTATUS;
typedef unsigned char BOOLEAN;
typedef int BOOL;
typedef void VOID;
typedef void* HANDLE;
typedef wchar_t WCHAR;
typedef WCHAR* LPWSTR;
typedef DWORD* LPDWORD;
typedef pthread_mutex_t CRITICAL_SECTION;
#define TRUE 1
#define FALSE 0
#define MAX_PATH 260
#define _wcsicmp wcscasecmp
#define _wcsnicmp wcsncasecmp
#define _stricmp strcasecmp
static void InitializeCriticalSection(CRITICAL_SECTION* lock) { CHECK(pthread_mutex_init(lock, NULL) == 0); }
static void EnterCriticalSection(CRITICAL_SECTION* lock) { CHECK(pthread_mutex_lock(lock) == 0); }
static void LeaveCriticalSection(CRITICAL_SECTION* lock) { CHECK(pthread_mutex_unlock(lock) == 0); }
static void DeleteCriticalSection(CRITICAL_SECTION* lock) { CHECK(pthread_mutex_destroy(lock) == 0); }
static WCHAR* _wcslwr(WCHAR* value) { for (WCHAR* p = value; *p; ++p) *p = towlower(*p); return value; }
#endif

#ifndef ARRAYSIZE
#define ARRAYSIZE(value) (sizeof(value) / sizeof((value)[0]))
#endif
#define NT_SUCCESS(status) ((status) >= 0)
#define _FX
#define Sbie_snwprintf swprintf
#define WITHOUT_POOL
#include "../../../common/map.c"

static HASH_MAP Kernel_DiskSN;
static CRITICAL_SECTION Kernel_DiskSN_CritSec;
#define Dll_Pool NULL
static THREAD_LOCAL ULONG LastErrorValue;
static THREAD_LOCAL int NameCalls;
static THREAD_LOCAL int NativeSawNull;
static ULONG RandomValue = 0x9000;
static WCHAR Paths[8][768] = {
	L"\\Device\\HarddiskVolume1\\first", L"\\Device\\HarddiskVolume2\\second",
	L"\\DEVICE\\HARDDISKVOLUME1\\\u00e9\u6f22", L"", L"ignored", L"not a native path",
	L"\\Device\\HarddiskVolume3", L"\\Device\\HarddiskVolume4"
};
static DWORD RealSerials[8] = {42, 42, 42, 42, 42, 42, 42, 42};
static const WCHAR* Serials[] = {L"1234-ABCD", L"5678-ABCD", L"", L"1234-ABCDE"};
static BOOL WriteOnFailure;
static BOOL ReturnNullName;
static BOOL NoTls;
static void MockSetLastError(ULONG value) { LastErrorValue = value; }
#define SetLastError MockSetLastError
#define GetLastError() LastErrorValue

typedef struct { int depth; } THREAD_DATA;
static THREAD_LOCAL THREAD_DATA Tls;
static THREAD_DATA* Dll_GetTlsData(ULONG* last)
{
	if (NoTls) return NULL;
	if (last) *last = LastErrorValue;
	return &Tls;
}
static void Dll_PushTlsNameBuffer(THREAD_DATA* data) { CHECK(data != NULL); ++data->depth; }
static void Dll_PopTlsNameBuffer(THREAD_DATA* data) { CHECK(data->depth > 0); --data->depth; }
static ULONG Dll_rand(void) { return ++RandomValue; }

static BOOL MockGetVolume(HANDLE handle, LPWSTR label, DWORD labelSize, LPDWORD serial,
	LPDWORD maxComponent, LPDWORD flags, LPWSTR fs, DWORD fsSize)
{
	NativeSawNull = serial == NULL;
	if ((uintptr_t)handle == 4) {
		if (WriteOnFailure && serial) *serial = 0xAABBCCDD;
		LastErrorValue = 123;
		return FALSE;
	}
	if (serial) *serial = RealSerials[(uintptr_t)handle];
	if (label && labelSize >= 2) { label[0] = L'V'; label[1] = 0; }
	if (fs && fsSize >= 2) { fs[0] = L'F'; fs[1] = 0; }
	if (maxComponent) *maxComponent = 255;
	if (flags) *flags = 0xABC;
	return TRUE;
}
#define __sys_GetVolumeInformationByHandleW MockGetVolume

static NTSTATUS File_GetName(HANDLE handle, void* object, WCHAR** real, WCHAR** copy, ULONG* flags)
{
	(void)object; (void)flags;
	++NameCalls;
	CHECK((uintptr_t)handle != 4);
	*copy = NULL;
	LastErrorValue = 456;
	if ((uintptr_t)handle == 3) { *real = NULL; return -1; }
	*real = ReturnNullName ? NULL : Paths[(uintptr_t)handle];
	return 0;
}
static BOOL SbieDll_GetSettingsForName(const WCHAR* box, const WCHAR* name,
	const WCHAR* setting, WCHAR* value, ULONG size, const WCHAR* fallback)
{
	(void)box; (void)setting; (void)fallback;
	LastErrorValue = 789;
	const WCHAR* names[] = {L"HarddiskVolume1", L"HarddiskVolume2", L"HarddiskVolume3", L"HarddiskVolume4"};
	for (size_t i = 0; i < ARRAYSIZE(names); ++i) {
		if (_wcsicmp(name, names[i]) == 0) {
			CHECK((wcslen(Serials[i]) + 1) * sizeof(WCHAR) <= size);
			wcscpy(value, Serials[i]);
			return TRUE;
		}
	}
	value[0] = 0;
	return FALSE;
}

#include "kernel_identity_under_test.inc"

static DWORD Query(uintptr_t handle)
{
	DWORD result = 0;
	LastErrorValue = 321;
	CHECK(Kernel_GetVolumeInformationByHandleW((HANDLE)handle, NULL, 0, &result, NULL, NULL, NULL, 0));
	CHECK(Tls.depth == 0);
	return result;
}
static void Collisions(void)
{
	CHECK(Query(0) == 0x1234ABCD);
	CHECK(Query(1) == 0x5678ABCD);
	CHECK(Query(2) == 0x1234ABCD);
	puts("PASS: distinct native volumes with equal serials, aliases and Unicode file paths");
}
static void Failure(void)
{
	DWORD serial = 0xDEADBEEF;
	int calls = NameCalls;
	CHECK(!Kernel_GetVolumeInformationByHandleW((HANDLE)4, NULL, 0, &serial, NULL, NULL, NULL, 0));
	CHECK(serial == 0xDEADBEEF && LastErrorValue == 123 && NameCalls == calls);
	WriteOnFailure = TRUE;
	CHECK(!Kernel_GetVolumeInformationByHandleW((HANDLE)4, NULL, 0, &serial, NULL, NULL, NULL, 0));
	CHECK(serial == 0xAABBCCDD && LastErrorValue == 123 && NameCalls == calls);
	LastErrorValue = 321;
	CHECK(Kernel_GetVolumeInformationByHandleW((HANDLE)5, NULL, 0, NULL, NULL, NULL, NULL, 0));
	CHECK(NativeSawNull && LastErrorValue == 321 && NameCalls == calls);
	WCHAR label[2], fs[2]; DWORD length = 0, flags = 0;
	CHECK(Kernel_GetVolumeInformationByHandleW((HANDLE)0, label, 2, &serial, &length, &flags, fs, 2));
	CHECK(wcscmp(label, L"V") == 0 && wcscmp(fs, L"F") == 0 && length == 255 && flags == 0xABC);
	CHECK(LastErrorValue == 321);
	puts("PASS: native failure outputs/error, null serial and unrelated output fields");
}
static void Names(void)
{
	DWORD fallback = Query(3);
	CHECK(Query(3) == fallback && Query(5) == fallback);
	ReturnNullName = TRUE;
	CHECK(Query(5) == fallback);
	ReturnNullName = FALSE;
	wmemcpy(Paths[5], L"\\Device\\", 8);
	for (size_t i = 8; i < 760; ++i) Paths[5][i] = L'x';
	Paths[5][760] = 0;
	CHECK(Query(5) == fallback);
	wcscpy(Paths[5], L"\\Device\\");
	CHECK(Query(5) == fallback);
	CHECK(Query(7) != 0x1234ABCD);
	map_clear(&Kernel_DiskSN);
	Serials[3] = L"12-34";
	CHECK(Query(7) == 0x1234);
	map_clear(&Kernel_DiskSN);
	Serials[3] = L"0000-0000";
	CHECK(Query(7) == 0 && Query(7) == 0);
	Serials[3] = L"1234-ABCDE";
	puts("PASS: failed, null, empty and oversized names; malformed, short and zero legacy serials");
}
static unsigned int ConstantHash(const void* key, size_t size)
{
	(void)key; (void)size;
	return 1;
}
static void HashCollisions(void)
{
	map_clear(&Kernel_DiskSN);
	unsigned int (*savedHash)(const void*, size_t) = Kernel_DiskSN.func_hash_key;
	Kernel_DiskSN.func_hash_key = ConstantHash;
	wcscpy(Paths[6], L"\\Device\\HarddiskVolume1234567890123456789\\file");
	CHECK(Query(0) == 0x1234ABCD);
	DWORD other = Query(6);
	CHECK(other != 0x1234ABCD && Query(6) == other);
	CHECK(Query(1) == 0x5678ABCD && Query(2) == 0x1234ABCD);
	map_clear(&Kernel_DiskSN);
	Kernel_DiskSN.func_hash_key = savedHash;
	wcscpy(Paths[6], L"\\Device\\HarddiskVolume3");
	puts("PASS: hash collisions between variable-length native volume keys");
}
static void Media(void)
{
	DWORD first = Query(6);
	CHECK(Query(6) == first);
	RealSerials[6] = 43;
	CHECK(Query(6) != first);
	wcscpy(Paths[6], L"\\Device\\HarddiskVolume2\\reused-handle");
	CHECK(Query(6) == 0x5678ABCD);
	puts("PASS: changed media serial and a handle reused for a different volume");
}
static void MissingTls(void)
{
	map_clear(&Kernel_DiskSN);
	NoTls = TRUE;
	int calls = NameCalls;
	DWORD serial = Query(0);
	CHECK(serial != RealSerials[0] && Query(0) == serial);
	CHECK(NameCalls == calls && LastErrorValue == 321);
	NoTls = FALSE;
	CHECK(Query(0) == 0x1234ABCD && LastErrorValue == 321);
	puts("PASS: unavailable TLS uses the unresolved-name fallback and preserves last error");
}
static int AllocationCalls;
static int FailAllocation;
static int LiveAllocations;
static void* FailingAllocator(void* pool, size_t size)
{
	(void)pool;
	if (++AllocationCalls == FailAllocation) return NULL;
	void* value = malloc(size);
	if (value) ++LiveAllocations;
	return value;
}
static void CountingFree(void* pool, void* value)
{
	(void)pool;
	if (value) --LiveAllocations;
	free(value);
}
static void AllocationFailure(void)
{
	wcscpy(Paths[6], L"\\Device\\HarddiskVolume3");
	RealSerials[6] = 42;
	map_clear(&Kernel_DiskSN);
	void* (*allocate)(void*, size_t) = Kernel_DiskSN.func_malloc;
	void (*release)(void*, void*) = Kernel_DiskSN.func_free;
	Kernel_DiskSN.func_malloc = FailingAllocator;
	Kernel_DiskSN.func_free = CountingFree;
	for (int failure = 1; failure <= 2; ++failure) {
		AllocationCalls = 0;
		FailAllocation = failure;
		CHECK(Query(0) == 0x1234ABCD && LastErrorValue == 321);
		CHECK(Kernel_DiskSN.nnodes == 0 && LiveAllocations == 0);
		FailAllocation = 0;
		CHECK(Query(0) == 0x1234ABCD && Kernel_DiskSN.nnodes == 1);
		map_clear(&Kernel_DiskSN);
		CHECK(LiveAllocations == 0);
	}
	AllocationCalls = 0;
	FailAllocation = 1;
	DWORD uncached = Query(6);
	CHECK(Kernel_DiskSN.nnodes == 0);
	FailAllocation = 0;
	DWORD cached = Query(6);
	CHECK(cached != uncached && Query(6) == cached);
	map_clear(&Kernel_DiskSN);
	CHECK(LiveAllocations == 0);
	Kernel_DiskSN.func_malloc = allocate;
	Kernel_DiskSN.func_free = release;
	puts("PASS: node/bucket allocation failure, cleanup and retry; random persistence is not guaranteed on failure");
}
#ifdef _WIN32
static DWORD WINAPI Worker(void* context)
#else
static void* Worker(void* context)
#endif
{
	(void)context;
	for (int i = 0; i < 2000; ++i) {
		CHECK(Query(0) == 0x1234ABCD);
		CHECK(Query(1) == 0x5678ABCD);
		CHECK(Query(2) == 0x1234ABCD);
	}
	return 0;
}
static void Concurrent(void)
{
	map_clear(&Kernel_DiskSN);
#ifdef _WIN32
	HANDLE threads[8];
	for (int i = 0; i < 8; ++i) { threads[i] = CreateThread(NULL, 0, Worker, NULL, 0, NULL); CHECK(threads[i]); }
	CHECK(WaitForMultipleObjects(8, threads, TRUE, INFINITE) == WAIT_OBJECT_0);
	for (int i = 0; i < 8; ++i) CloseHandle(threads[i]);
#else
	pthread_t threads[8];
	for (int i = 0; i < 8; ++i) CHECK(pthread_create(&threads[i], NULL, Worker, NULL) == 0);
	for (int i = 0; i < 8; ++i) CHECK(pthread_join(threads[i], NULL) == 0);
#endif
	puts("PASS: concurrent cold-cache initialization and 48000 reads");
}
int main(int argc, char** argv)
{
	const char* test = argc > 1 ? argv[1] : "all";
	if (argc > 2 || (strcmp(test, "all") && strcmp(test, "collisions")
		&& strcmp(test, "failure") && strcmp(test, "names") && strcmp(test, "hash")
		&& strcmp(test, "media") && strcmp(test, "concurrent")
		&& strcmp(test, "tls") && strcmp(test, "allocation"))) {
		fputs("Unknown test name or unexpected arguments\n", stderr);
		return 2;
	}
#include "kernel_identity_init.inc"
	if (!strcmp(test, "all") || !strcmp(test, "collisions")) Collisions();
	if (!strcmp(test, "all") || !strcmp(test, "failure")) Failure();
	if (!strcmp(test, "all") || !strcmp(test, "names")) Names();
	if (!strcmp(test, "all") || !strcmp(test, "hash")) HashCollisions();
	if (!strcmp(test, "all") || !strcmp(test, "media")) Media();
	if (!strcmp(test, "all") || !strcmp(test, "concurrent")) Concurrent();
	if (!strcmp(test, "all") || !strcmp(test, "tls")) MissingTls();
	if (!strcmp(test, "all") || !strcmp(test, "allocation")) AllocationFailure();
	map_clear(&Kernel_DiskSN);
	DeleteCriticalSection(&Kernel_DiskSN_CritSec);
	return 0;
}
