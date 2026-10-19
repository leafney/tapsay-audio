/*
 * TapSay Audio HAL contract checks.
 * This test includes the derived driver source so callbacks can be checked
 * without installing anything into the system HAL directory.
 */

#include <assert.h>
#include <math.h>
#include <stdio.h>

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

static void expect_one_device(AudioObjectID object_id, AudioObjectPropertySelector selector)
{
    AudioObjectPropertyAddress address = property(selector, kAudioObjectPropertyScopeGlobal);
    AudioObjectID objects[4] = { 0, 0, 0, 0 };
    UInt32 size = sizeof(objects);
    OSStatus status = TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, object_id, 0, &address, 0, NULL, sizeof(objects), &size, objects
    );
    assert(status == noErr);
    assert(size == sizeof(AudioObjectID));
    assert(objects[0] == kObjectID_Device);
}

static void check_identity_and_enumeration(void)
{
    AudioObjectPropertyAddress address = property(kAudioPlugInPropertyDeviceList, kAudioObjectPropertyScopeGlobal);
    AudioObjectID device_ids[4] = { 0, 0, 0, 0 };
    UInt32 size = sizeof(device_ids);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_PlugIn, 0, &address, 0, NULL,
        sizeof(device_ids), &size, device_ids
    ) == noErr);
    assert(size == sizeof(AudioObjectID));
    assert(device_ids[0] == kObjectID_Device);

    expect_one_device(kObjectID_Box, kAudioBoxPropertyDeviceList);

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

    expect_string(kObjectID_Device, kAudioDevicePropertyDeviceUID, "com.leafney.tapsay.audio.device.2ch");
    expect_string(kObjectID_Device, kAudioDevicePropertyModelUID, "com.leafney.tapsay.audio.model.2ch");
    expect_string(kObjectID_Box, kAudioBoxPropertyBoxUID, "com.leafney.tapsay.audio.box");
    expect_string(kObjectID_Device, kAudioObjectPropertyName, "TapSay Audio 2ch");
    expect_string(kObjectID_Device, kAudioObjectPropertyManufacturer, "TapSay");
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

    address = property(kAudioDevicePropertyNominalSampleRate, kAudioObjectPropertyScopeGlobal);
    Float64 sample_rate = 0;
    size = sizeof(sample_rate);
    assert(TapSayAudio_GetPropertyData(
        gAudioServerPlugInDriverRef, kObjectID_Device, 0, &address, 0, NULL,
        sizeof(sample_rate), &size, &sample_rate
    ) == noErr);
    assert(sample_rate == 16000.0);
}

static void check_supported_formats(void)
{
    const Float64 expected_rates[] = { 16000.0, 44100.0, 48000.0 };
    const UInt32 expected_flags =
        kAudioFormatFlagIsFloat | kAudioFormatFlagsNativeEndian | kAudioFormatFlagIsPacked;

    const AudioObjectID stream_ids[] = { kObjectID_Stream_Input, kObjectID_Stream_Output };
    for (size_t stream_index = 0; stream_index < 2; stream_index++) {
        AudioObjectID stream_id = stream_ids[stream_index];
        AudioObjectPropertyAddress address = property(
            kAudioStreamPropertyAvailableVirtualFormats, kAudioObjectPropertyScopeGlobal
        );
        AudioStreamRangedDescription formats[4] = { 0 };
        UInt32 size = sizeof(formats);
        assert(TapSayAudio_GetPropertyData(
            gAudioServerPlugInDriverRef, stream_id, 0, &address, 0, NULL,
            sizeof(formats), &size, formats
        ) == noErr);
        assert(size == 3 * sizeof(AudioStreamRangedDescription));

        for (UInt32 index = 0; index < 3; index++) {
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

int main(void)
{
    check_identity_and_enumeration();
    check_transport_and_default_rate();
    check_supported_formats();
    check_control_defaults();
    puts("TapSay Audio HAL contract checks passed");
    return 0;
}
