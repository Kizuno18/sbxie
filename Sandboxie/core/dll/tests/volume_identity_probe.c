// SPDX-License-Identifier: GPL-3.0-or-later
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winternl.h>
#include <stddef.h>
#include <stdio.h>
#include <wchar.h>

#define COUNT(value) (sizeof(value) / sizeof((value)[0]))
#define SAMPLE_COUNT 32

typedef BOOL (WINAPI *PVolumeByHandle)(HANDLE, LPWSTR, DWORD, LPDWORD, LPDWORD, LPDWORD, LPWSTR, DWORD);
typedef NTSTATUS (NTAPI *PQueryVolume)(HANDLE, PIO_STATUS_BLOCK, PVOID, ULONG, int);

typedef struct {
	LARGE_INTEGER CreationTime;
	ULONG Serial;
	ULONG LabelLength;
	BOOLEAN SupportsObjects;
	WCHAR Label[1];
} SVolumeInformation;
typedef char CheckSerialOffset[offsetof(SVolumeInformation, Serial) == 8 ? 1 : -1];
typedef char CheckLabelOffset[offsetof(SVolumeInformation, Label) == 18 ? 1 : -1];

typedef struct {
	const char* Name;
	BOOL Available;
	BOOL Success;
	BOOL Stable;
	DWORD Serial;
	DWORD Error;
} SObservation;

static PVolumeByHandle ByHandle;
static PQueryVolume Native;
static WCHAR Root[32768];
static char AnsiRoot[65536];

static const char* Boolean(BOOL value) { return value ? "true" : "false"; }

static HANDLE OpenPath(const WCHAR* path)
{
	return CreateFileW(path, FILE_READ_ATTRIBUTES,
		FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
		OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
}

static BOOL ReadSerial(int method, HANDLE file, DWORD* serial, DWORD* error)
{
	BOOL result = FALSE;
	SetLastError(0);
	switch (method) {
	case 0:
		result = ByHandle(file, NULL, 0, serial, NULL, NULL, NULL, 0);
		break;
	case 1:
		result = GetVolumeInformationW(Root, NULL, 0, serial, NULL, NULL, NULL, 0);
		break;
	case 2:
		result = GetVolumeInformationA(AnsiRoot, NULL, 0, serial, NULL, NULL, NULL, 0);
		break;
	case 3: {
		union { LARGE_INTEGER Align; BYTE Data[4096]; } buffer = {0};
		IO_STATUS_BLOCK io = {0};
		NTSTATUS status = Native(file, &io, buffer.Data, sizeof(buffer.Data), 1);
		if (status != 0 || io.Information < offsetof(SVolumeInformation, Label)
			|| io.Information > sizeof(buffer.Data)) {
			*error = status != 0 ? (DWORD)status : ERROR_INVALID_DATA;
			return FALSE;
		}
		*serial = ((SVolumeInformation*)buffer.Data)->Serial;
		*error = 0;
		return TRUE;
	}
	case 4: {
		BY_HANDLE_FILE_INFORMATION info;
		result = GetFileInformationByHandle(file, &info);
		if (result) *serial = info.dwVolumeSerialNumber;
		break;
	}
	}
	*error = result ? 0 : GetLastError();
	return result;
}

static SObservation Observe(const char* name, int method, HANDLE file, BOOL available)
{
	SObservation observation = {name, available, FALSE, FALSE, 0, 0};
	if (!available) return observation;
	for (int sample = 0; sample < SAMPLE_COUNT; ++sample) {
		DWORD serial;
		if (!ReadSerial(method, file, &serial, &observation.Error)) return observation;
		if (sample == 0) {
			observation.Serial = serial;
			observation.Stable = TRUE;
		} else if (serial != observation.Serial) observation.Stable = FALSE;
	}
	observation.Success = TRUE;
	return observation;
}

static const char* Same(const SObservation* first, const SObservation* second)
{
	if (!first->Success || !second->Success) return "null";
	return Boolean(first->Serial == second->Serial);
}

static BOOL ParseSerial(const WCHAR* text, DWORD* value)
{
	size_t length = wcslen(text);
	if (length != 8 && length != 9) return FALSE;
	DWORD result = 0;
	for (size_t i = 0; i < length; ++i) {
		WCHAR c = text[i];
		if (length == 9 && i == 4) { if (c != L'-') return FALSE; else continue; }
		unsigned int digit;
		if (c >= L'0' && c <= L'9') digit = c - L'0';
		else if (c >= L'a' && c <= L'f') digit = c - L'a' + 10;
		else if (c >= L'A' && c <= L'F') digit = c - L'A' + 10;
		else return FALSE;
		result = (result << 4) | digit;
	}
	*value = result;
	return TRUE;
}

static int Error(const char* operation, DWORD code)
{
	printf("{\"version\":1,\"error\":\"%s\",\"code\":%lu}\n", operation, (unsigned long)code);
	return 2;
}

int wmain(int argc, WCHAR** argv)
{
	const WCHAR* path = L".";
	BOOL havePath = FALSE, haveExpected = FALSE, requireSandbox = FALSE, requireCoherent = FALSE;
	DWORD expected = 0;
	for (int i = 1; i < argc; ++i) {
		if (!wcscmp(argv[i], L"--path") && !havePath && i + 1 < argc) {
			path = argv[++i]; havePath = TRUE;
		} else if (!wcscmp(argv[i], L"--expect-by-handle") && !haveExpected && i + 1 < argc) {
			if (!ParseSerial(argv[++i], &expected)) return Error("invalid_expected_serial", ERROR_INVALID_PARAMETER);
			haveExpected = TRUE;
		} else if (!wcscmp(argv[i], L"--require-sandbox") && !requireSandbox) requireSandbox = TRUE;
		else if (!wcscmp(argv[i], L"--require-coherent") && !requireCoherent) requireCoherent = TRUE;
		else return Error("invalid_arguments", ERROR_INVALID_PARAMETER);
	}

	BOOL loaded = GetModuleHandleW(L"SbieDll.dll") != NULL;
	if (requireSandbox && !loaded) return Error("sandbox_module_missing", ERROR_MOD_NOT_FOUND);
	HMODULE kernel = GetModuleHandleW(L"kernel32.dll");
	HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
	ByHandle = (PVolumeByHandle)GetProcAddress(kernel, "GetVolumeInformationByHandleW");
	Native = (PQueryVolume)GetProcAddress(ntdll, "NtQueryVolumeInformationFile");
	HANDLE file = OpenPath(path);
	if (file == INVALID_HANDLE_VALUE) return Error("open_path", GetLastError());

	WCHAR finalPath[32768];
	DWORD length = GetFinalPathNameByHandleW(file, finalPath, COUNT(finalPath), FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
	if (!length || length >= COUNT(finalPath)) {
		DWORD code = length ? ERROR_INSUFFICIENT_BUFFER : GetLastError();
		CloseHandle(file); return Error("resolve_path", code);
	}
	if (!GetVolumePathNameW(finalPath, Root, COUNT(Root))) {
		DWORD code = GetLastError(); CloseHandle(file); return Error("resolve_volume", code);
	}
	BOOL usedDefault = FALSE;
	BOOL utf8 = GetACP() == CP_UTF8;
	BOOL ansi = WideCharToMultiByte(CP_ACP, utf8 ? 0 : WC_NO_BEST_FIT_CHARS,
		Root, -1, AnsiRoot, COUNT(AnsiRoot), NULL, utf8 ? NULL : &usedDefault) > 0 && !usedDefault;
	const char* names[] = {"by_handle", "path_w", "path_a", "native", "file_information"};
	BOOL available[] = {ByHandle != NULL, TRUE, ansi, Native != NULL, TRUE};
	SObservation observations[5];
	for (int method = 0; method < 5; ++method)
		observations[method] = Observe(names[method], method, file, available[method]);

	SObservation duplicate = {"duplicate", FALSE, FALSE, FALSE, 0, 0};
	HANDLE other;
	if (ByHandle && DuplicateHandle(GetCurrentProcess(), file, GetCurrentProcess(), &other, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
		duplicate = Observe("duplicate", 0, other, TRUE);
		CloseHandle(other);
	}
	CloseHandle(file);
	other = OpenPath(finalPath);
	SObservation reopened = {"reopened", FALSE, FALSE, FALSE, 0, 0};
	if (other != INVALID_HANDLE_VALUE) {
		if (ByHandle) reopened = Observe("reopened", 0, other, TRUE);
		CloseHandle(other);
	}

	BOOL allSucceeded = TRUE, allStable = TRUE, coherent = TRUE;
	for (int method = 0; method < 5; ++method) {
		allSucceeded = allSucceeded && observations[method].Success;
		allStable = allStable && observations[method].Stable;
		coherent = coherent && observations[method].Serial == observations[0].Serial;
	}
	BOOL handleChecks = duplicate.Success && reopened.Success && duplicate.Stable && reopened.Stable
		&& duplicate.Serial == observations[0].Serial && reopened.Serial == observations[0].Serial;
	BOOL matchesExpected = observations[0].Success && observations[0].Stable && observations[0].Serial == expected;
	BOOL passed = observations[0].Success && observations[0].Stable && handleChecks
		&& (!haveExpected || matchesExpected) && (!requireCoherent || (allSucceeded && allStable && coherent));

	printf("{\"version\":1,\"sbieDllLoaded\":%s,\"samplesPerQuery\":%d,\"queries\":{", Boolean(loaded), SAMPLE_COUNT);
	for (int method = 0; method < 5; ++method) {
		SObservation* item = &observations[method];
		printf("%s\"%s\":{\"available\":%s,\"success\":%s,\"stable\":%s,\"error\":%lu}",
			method ? "," : "", item->Name, Boolean(item->Available), Boolean(item->Success),
			item->Success ? Boolean(item->Stable) : "null", (unsigned long)item->Error);
	}
	printf("},\"sameAsByHandle\":{\"path_w\":%s,\"path_a\":%s,\"native\":%s,\"file_information\":%s},",
		Same(&observations[0], &observations[1]), Same(&observations[0], &observations[2]),
		Same(&observations[0], &observations[3]), Same(&observations[0], &observations[4]));
	printf("\"duplicateStable\":%s,\"reopenedStable\":%s,\"coherent\":%s,\"expectedSatisfied\":%s,\"requestedChecksPassed\":%s}\n",
		duplicate.Success ? Boolean(duplicate.Stable && duplicate.Serial == observations[0].Serial) : "null",
		reopened.Success ? Boolean(reopened.Stable && reopened.Serial == observations[0].Serial) : "null",
		allSucceeded ? Boolean(allStable && coherent) : "null", haveExpected ? Boolean(matchesExpected) : "null", Boolean(passed));
	return passed ? 0 : 1;
}
