/*
 * TapSay Audio HAL contract checks.
 * This test includes the derived driver source so callbacks can be checked
 * without installing anything into the system HAL directory.
 */

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../TapSayAudio/TapSayAudio.c"

static AudioObjectPropertyAddress property(AudioObjectPropertySelector selector, AudioObjectPropertyScope scope)
{
    AudioObjectPropertyAddress address = {
        .mSelector = selector,
        .mScope = scope,
        .mElement = kAudioObjectPropertyElementMain,
    };
    return address;
}

static void expect_string(AudioObjectID object_id, AudioObjectPropertySelector selector, const char *expected)
{
    AudioObjectPropertyAddress address = property(selector, kAudioObjectPropertyScopeGlobal);
    CFStringRef actual = NULL;
    CFStringRef expected_string = CFStringCreateWithCString(NULL, expected, kCFStringEncodingUTF8);
    UInt32 size = sizeof(actual);
    OSStatus status = TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, object_id, 0, &address, 0, NULL, sizeof(actual), &size, &actual
    );
    assert(status == noErr);
    assert(size == sizeof(actual));
    assert(CFStringCompare(actual, expected_string, 0) == kCFCompareEqualTo);
    CFRelease(actual);
    CFRelease(expected_string);
}

static void expect_device_list(AudioObjectID object_id, AudioObjectPropertySelector selector, UInt32 capacity, UInt32 expected_count)
{
    AudioObjectPropertyAddress address = property(selector, kAudioObjectPropertyScopeGlobal);
    AudioObjectID objects[4] = { 0, 0, 0, 0 };
    UInt32 size = capacity * sizeof(AudioObjectID);
    OSStatus status = TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, object_id, 0, &address, 0, NULL, size, &size, objects
    );
    assert(status == noErr);
    assert(size == expected_count * sizeof(AudioObjectID));
    if (expected_count > 0) assert(objects[0] == kObjectID_Device);
    if (expected_count > 1) assert(objects[1] == kObjectID_Device2);
}

static AudioObjectID translate_device_uid(const char *uid)
{
    AudioObjectPropertyAddress address = property(
        kAudioPlugInPropertyTranslateUIDToDevice, kAudioObjectPropertyScopeGlobal
    );
    CFStringRef qualifier_uid = CFStringCreateWithCString(NULL, uid, kCFStringEncodingUTF8);
    AudioObjectID translated = kAudioObjectUnknown;
    UInt32 size = sizeof(translated);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_PlugIn, 0, &address,
        sizeof(qualifier_uid), &qualifier_uid, sizeof(translated), &size, &translated
    ) == noErr);
    CFRelease(qualifier_uid);
    assert(size == sizeof(translated));
    return translated;
}

static void check_owned_object_capacity(AudioObjectID object_id, UInt32 expected_count)
{
    AudioObjectPropertyAddress address = property(
        kAudioObjectPropertyOwnedObjects, kAudioObjectPropertyScopeGlobal
    );
    AudioObjectID objects[16] = { 0 };
    UInt32 capacities[] = { 0, 1, expected_count, 16 };
    for (size_t index = 0; index < sizeof(capacities) / sizeof(capacities[0]); index++) {
        UInt32 capacity = capacities[index];
        UInt32 size = capacity * sizeof(AudioObjectID);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, object_id, 0, &address, 0, NULL,
            size, &size, objects
        ) == noErr);
        UInt32 expected = capacity < expected_count ? capacity : expected_count;
        assert(size == expected * sizeof(AudioObjectID));
    }
}

static void check_identity_and_enumeration(void)
{
    assert(kDevice_RingBufferSize == 16384);
    assert(kRing_Buffer_Frame_Size == 65536);
    assert(kLatency_Frame_Size == 0);
    assert(device_object_list_size(kAudioObjectPropertyScopeGlobal, kObjectID_Device) > 0);

    AudioObjectPropertyAddress address = property(kAudioPlugInPropertyDeviceList, kAudioObjectPropertyScopeGlobal);
    AudioObjectID device_ids[4] = { 0, 0, 0, 0 };
    UInt32 size = sizeof(device_ids);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_PlugIn, 0, &address, 0, NULL,
        sizeof(device_ids), &size, device_ids
    ) == noErr);
    assert(size == (TAPSAY_ENABLE_REFERENCE_PROFILE ? 2 : 1) * sizeof(AudioObjectID));
    assert(device_ids[0] == kObjectID_Device);
    if (TAPSAY_ENABLE_REFERENCE_PROFILE) assert(device_ids[1] == kObjectID_Device2);

    UInt32 count = TAPSAY_ENABLE_REFERENCE_PROFILE ? 2 : 1;
    expect_device_list(kObjectID_PlugIn, kAudioPlugInPropertyDeviceList, 0, 0);
    expect_device_list(kObjectID_PlugIn, kAudioPlugInPropertyDeviceList, 1, 1);
    expect_device_list(kObjectID_PlugIn, kAudioPlugInPropertyDeviceList, 2, count);
    expect_device_list(kObjectID_Box, kAudioBoxPropertyDeviceList, 0, 0);
    expect_device_list(kObjectID_Box, kAudioBoxPropertyDeviceList, 1, 1);
    expect_device_list(kObjectID_Box, kAudioBoxPropertyDeviceList, 2, count);

    address = property(kAudioObjectPropertyOwnedObjects, kAudioObjectPropertyScopeGlobal);
    AudioObjectID owned_objects[4] = { 0, 0, 0, 0 };
    size = sizeof(owned_objects);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_PlugIn, 0, &address, 0, NULL,
        sizeof(owned_objects), &size, owned_objects
    ) == noErr);
    assert(size == 2 * sizeof(AudioObjectID));
    assert(owned_objects[0] == kObjectID_Box);
    assert(owned_objects[1] == kObjectID_Device);
    check_owned_object_capacity(kObjectID_PlugIn, 2);

    expect_string(kObjectID_Device, kAudioDevicePropertyDeviceUID, kDevice_UID);
    expect_string(kObjectID_Device, kAudioDevicePropertyModelUID, kDevice_ModelUID);
    expect_string(kObjectID_Box, kAudioBoxPropertyBoxUID, kBox_UID);
    expect_string(kObjectID_Device, kAudioObjectPropertyName, kDevice_Name);
    expect_string(kObjectID_Device, kAudioObjectPropertyManufacturer, kManufacturer_Name);
    assert(translate_device_uid(kDevice_UID) == kObjectID_Device);
    assert(translate_device_uid("com.leafney.tapsay.audio.unknown") == kAudioObjectUnknown);
    if (TAPSAY_ENABLE_REFERENCE_PROFILE) {
        assert(device_object_list_size(kAudioObjectPropertyScopeGlobal, kObjectID_Device2) > 0);
        expect_string(kObjectID_Device2, kAudioDevicePropertyDeviceUID, kDevice2_UID);
        expect_string(kObjectID_Device2, kAudioObjectPropertyName, kDevice2_Name);
        assert(translate_device_uid(kDevice2_UID) == kObjectID_Device2);
        check_owned_object_capacity(kObjectID_Device2, kDevice2_ObjectListSize);

        assert(TapSayAudio_HasProperty(
            gAudioServerPlugInDriverRef, kObjectID_Device2, 0,
            &address
        ));
        AudioObjectID streams[4] = { 0 };
        address = property(kAudioDevicePropertyStreams, kAudioObjectPropertyScopeGlobal);
        size = sizeof(streams);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, kObjectID_Device2, 0, &address, 0, NULL,
            sizeof(streams), &size, streams
        ) == noErr);
        assert(size == 2 * sizeof(AudioObjectID));
        assert(streams[0] == kObjectID_Stream_Input);
        assert(streams[1] == kObjectID_Stream_Output);

        AudioObjectID controls[8] = { 0 };
        address = property(kAudioObjectPropertyControlList, kAudioObjectPropertyScopeGlobal);
        size = sizeof(controls);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, kObjectID_Device2, 0, &address, 0, NULL,
            sizeof(controls), &size, controls
        ) == noErr);
        assert(size == device_control_list_size(kAudioObjectPropertyScopeGlobal, kObjectID_Device2)
            * sizeof(AudioObjectID));

        address = property(kAudioDevicePropertyIsHidden, kAudioObjectPropertyScopeGlobal);
        UInt32 hidden = 0;
        size = sizeof(hidden);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, kObjectID_Device2, 0, &address, 0, NULL,
            sizeof(hidden), &size, &hidden
        ) == noErr);
        assert(hidden == 1);
    }
}

static void check_transport_and_default_rate(void)
{
    AudioObjectPropertyAddress address = property(kAudioDevicePropertyTransportType, kAudioObjectPropertyScopeGlobal);
    UInt32 transport = 0;
    UInt32 size = sizeof(transport);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Device, 0, &address, 0, NULL,
        sizeof(transport), &size, &transport
    ) == noErr);
    assert(transport == kAudioDeviceTransportTypeUSB);

    address = property(kAudioBoxPropertyTransportType, kAudioObjectPropertyScopeGlobal);
    transport = 0;
    size = sizeof(transport);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Box, 0, &address, 0, NULL,
        sizeof(transport), &size, &transport
    ) == noErr);
    assert(transport == TAPSAY_BOX_TRANSPORT_TYPE);

    address = property(kAudioDevicePropertyNominalSampleRate, kAudioObjectPropertyScopeGlobal);
    Float64 sample_rate = 0;
    size = sizeof(sample_rate);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Device, 0, &address, 0, NULL,
        sizeof(sample_rate), &size, &sample_rate
    ) == noErr);
    assert(sample_rate == TAPSAY_DEFAULT_SAMPLE_RATE);
}

static void check_supported_formats(void)
{
    const Float64 expected_rates[] = { kSampleRates };
    const UInt32 expected_flags =
        kAudioFormatFlagIsFloat | kAudioFormatFlagsNativeEndian | kAudioFormatFlagIsPacked;

    const AudioObjectID stream_ids[] = { kObjectID_Stream_Input, kObjectID_Stream_Output };
    for (size_t index = 0; index < sizeof(expected_rates) / sizeof(expected_rates[0]); index++) {
        assert(is_valid_sample_rate(expected_rates[index]));
    }
    assert(!is_valid_sample_rate(32000.0));

    for (size_t stream_index = 0; stream_index < 2; stream_index++) {
        AudioObjectID stream_id = stream_ids[stream_index];
        AudioObjectPropertyAddress address = property(
            kAudioStreamPropertyAvailableVirtualFormats, kAudioObjectPropertyScopeGlobal
        );
        AudioStreamRangedDescription formats[16] = { 0 };
        UInt32 size = sizeof(formats);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, stream_id, 0, &address, 0, NULL,
            sizeof(formats), &size, formats
        ) == noErr);
        assert(size == sizeof(expected_rates) / sizeof(expected_rates[0]) * sizeof(AudioStreamRangedDescription));

        for (UInt32 index = 0; index < sizeof(expected_rates) / sizeof(expected_rates[0]); index++) {
            assert(formats[index].mFormat.mSampleRate == expected_rates[index]);
            assert(formats[index].mFormat.mChannelsPerFrame == 2);
            assert(formats[index].mFormat.mBitsPerChannel == 32);
            assert(formats[index].mFormat.mFormatFlags == expected_flags);
            assert(formats[index].mSampleRateRange.mMinimum == expected_rates[index]);
            assert(formats[index].mSampleRateRange.mMaximum == expected_rates[index]);
        }
    }
}

static void check_control_defaults(void)
{
    AudioObjectPropertyAddress address = property(
        kAudioLevelControlPropertyScalarValue, kAudioObjectPropertyScopeInput
    );
    Float32 input_volume = 0;
    UInt32 size = sizeof(input_volume);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Volume_Input_Master, 0, &address, 0, NULL,
        sizeof(input_volume), &size, &input_volume
    ) == noErr);
    assert(fabsf(input_volume - 1.0f) < 0.0001f);

    address = property(kAudioBooleanControlPropertyValue, kAudioObjectPropertyScopeInput);
    UInt32 input_mute = 1;
    size = sizeof(input_mute);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Mute_Input_Master, 0, &address, 0, NULL,
        sizeof(input_mute), &size, &input_mute
    ) == noErr);
    assert(input_mute == 0);
}

static void check_pcm_ring_buffer_round_trip(AudioObjectID device_id)
{
    assert(TapSayAudio_StartIO(gAudioServerPlugInDriverRef, device_id, 1) == noErr);
    const UInt32 frames = 4;
    Float32 input[frames * kNumber_Of_Channels] = {
        0.1f, -0.1f, 0.2f, -0.2f, 0.3f, -0.3f, 0.4f, -0.4f
    };
    Float32 output[frames * kNumber_Of_Channels] = { 0 };
    AudioServerPlugInIOCycleInfo cycle = { 0 };
    cycle.mCurrentTime.mSampleTime = 0;
    cycle.mOutputTime.mSampleTime = 0;
    assert(TapSayAudio_DoIOOperation(
        gAudioServerPlugInDriverRef, device_id, kObjectID_Stream_Output,
        0, kAudioServerPlugInIOOperationWriteMix, frames, &cycle, input, NULL
    ) == noErr);

    cycle.mInputTime.mSampleTime = 0;
    assert(TapSayAudio_DoIOOperation(
        gAudioServerPlugInDriverRef, device_id, kObjectID_Stream_Input,
        0, kAudioServerPlugInIOOperationReadInput, frames, &cycle, output, NULL
    ) == noErr);
    assert(memcmp(input, output, sizeof(input)) == 0);

    const UInt64 wrap_start = kRing_Buffer_Frame_Size - 2;
    cycle.mCurrentTime.mSampleTime = wrap_start;
    cycle.mOutputTime.mSampleTime = wrap_start;
    assert(TapSayAudio_DoIOOperation(
        gAudioServerPlugInDriverRef, kObjectID_Device, kObjectID_Stream_Output,
        0, kAudioServerPlugInIOOperationWriteMix, frames, &cycle, input, NULL
    ) == noErr);
    cycle.mInputTime.mSampleTime = wrap_start;
    memset(output, 0, sizeof(output));
    assert(TapSayAudio_DoIOOperation(
        gAudioServerPlugInDriverRef, kObjectID_Device, kObjectID_Stream_Input,
        0, kAudioServerPlugInIOOperationReadInput, frames, &cycle, output, NULL
    ) == noErr);
    assert(memcmp(input, output, sizeof(input)) == 0);
    assert(TapSayAudio_StopIO(gAudioServerPlugInDriverRef, device_id, 1) == noErr);
}

int main(int argc, char **argv)
{
    const char *requested_profile = argc > 1 ? argv[1] : "legacy";
    assert(strcmp(requested_profile, TAPSAY_PROFILE_NAME) == 0);
    check_identity_and_enumeration();
    check_transport_and_default_rate();
    check_supported_formats();
    check_control_defaults();
    check_pcm_ring_buffer_round_trip(kObjectID_Device);
    if (TAPSAY_ENABLE_REFERENCE_PROFILE) {
        check_pcm_ring_buffer_round_trip(kObjectID_Device2);
    }
    puts("TapSay Audio HAL contract checks passed");
    return 0;
}
