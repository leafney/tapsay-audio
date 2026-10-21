// SPDX-License-Identifier: GPL-3.0-only
// Direct callbacks run only in this isolated executable, never in coreaudiod.
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include TAPSAY_DRIVER_SOURCE

static OSStatus get(AudioObjectID object, AudioObjectPropertySelector selector,
                    AudioObjectPropertyScope scope, UInt32 capacity, UInt32 *written,
                    void *data) {
    AudioObjectPropertyAddress address = {selector, scope, kAudioObjectPropertyElementMain};
    return (*gAudioServerPlugInDriverRef)->GetPropertyData(
        gAudioServerPlugInDriverRef, object, 0, &address, 0, NULL, capacity, written, data);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (strcmp(argv[1], "control-matrix") == 0) {
        const AudioObjectID objects[] = {kObjectID_Device, kObjectID_Device2};
        const AudioObjectPropertyScope scopes[] = {kAudioObjectPropertyScopeGlobal,
            kAudioObjectPropertyScopeInput, kAudioObjectPropertyScopeOutput};
        unsigned cases = 0;
        for (unsigned enabled = 0; enabled < 2; enabled++) {
            assert((*gAudioServerPlugInDriverRef)->PerformDeviceConfigurationChange(
                gAudioServerPlugInDriverRef, kObjectID_Device,
                enabled ? ChangeAction_EnablePitchControl : ChangeAction_DisablePitchControl,
                NULL) == noErr);
            for (unsigned device = 0; device < 2; device++) {
                for (unsigned scope = 0; scope < 3; scope++) {
                    AudioObjectID expected[6];
                    unsigned count = 0;
                    if (scope == 0 || scope == 1) {
                        expected[count++] = kObjectID_Volume_Input_Master;
                        expected[count++] = kObjectID_Mute_Input_Master;
                    }
                    if (scope == 0 || scope == 2) {
                        expected[count++] = kObjectID_Volume_Output_Master;
                        expected[count++] = kObjectID_Mute_Output_Master;
                        if (enabled && device == 0) expected[count++] = kObjectID_Pitch_Adjust;
                    }
                    if (scope == 0 && device == 0) expected[count++] = kObjectID_ClockSource;
                    AudioObjectPropertyAddress address = {kAudioObjectPropertyControlList,
                        scopes[scope], kAudioObjectPropertyElementMain};
                    UInt32 size = 0;
                    assert((*gAudioServerPlugInDriverRef)->GetPropertyDataSize(
                        gAudioServerPlugInDriverRef, objects[device], 0, &address,
                        0, NULL, &size) == noErr);
                    assert(size == count * sizeof(AudioObjectID));
                    UInt32 capacities[] = {0, 1, 4, size, size + 16};
                    for (unsigned capacity = 0; capacity < 5; capacity++) {
                        AudioObjectID ids[16];
                        for (unsigned i = 0; i < 16; i++) ids[i] = 0xa55aa55a;
                        UInt32 written = 0;
                        assert(get(objects[device], address.mSelector, address.mScope,
                                   capacities[capacity], &written, ids) == noErr);
                        UInt32 returned = capacities[capacity] / sizeof(AudioObjectID);
                        if (returned > count) returned = count;
                        assert(written == returned * sizeof(AudioObjectID));
                        for (unsigned i = 0; i < returned; i++) assert(ids[i] == expected[i]);
                        for (unsigned i = returned; i < 16; i++) assert(ids[i] == 0xa55aa55a);
                        cases++;
                    }
                }
            }
        }
        printf("control-matrix: PASS (%u cases)\n", cases);
        return 0;
    }
    if (strcmp(argv[1], "control-list") == 0) {
        AudioObjectPropertyAddress address = {
            kAudioObjectPropertyControlList, kAudioObjectPropertyScopeGlobal,
            kAudioObjectPropertyElementMain};
        UInt32 size = 0, written = 0;
        assert((*gAudioServerPlugInDriverRef)->GetPropertyDataSize(
            gAudioServerPlugInDriverRef, kObjectID_Device, 0, &address, 0, NULL, &size) == noErr);
        AudioObjectID ids[32] = {0};
        assert(size <= sizeof(ids));
        printf("control-list: advertised=%u bytes, pitch-enabled=%d\n", size, gPitch_Adjust_Enabled);
        fflush(stdout);
        assert(get(kObjectID_Device, address.mSelector, address.mScope, size, &written, ids) == noErr);
        assert(written == size);
        for (UInt32 i = 0; i < written / sizeof(AudioObjectID); i++) {
            assert(ids[i] != 0 && ids[i] != kObjectID_Pitch_Adjust);
        }
        puts("control-list: PASS");
        return 0;
    }
    if (strcmp(argv[1], "formats") == 0) {
        const Float64 expected[] = {8000, 16000, 24000, 44100, 48000, 88200, 96000,
            176400, 192000, 352800, 384000, 705600, 768000};
        AudioValueRange ranges[13];
        UInt32 written = 0;
        assert(get(kObjectID_Device, kAudioDevicePropertyAvailableNominalSampleRates,
                   kAudioObjectPropertyScopeGlobal, sizeof(ranges), &written, ranges) == noErr);
        assert(written == sizeof(ranges));
        Float64 initial = 0;
        assert(get(kObjectID_Device, kAudioDevicePropertyNominalSampleRate,
                   kAudioObjectPropertyScopeGlobal, sizeof(initial), &written, &initial) == noErr);
        assert(initial == 48000);
        for (unsigned i = 0; i < 13; i++) {
            assert(ranges[i].mMinimum == expected[i] && ranges[i].mMaximum == expected[i]);
            for (unsigned stream = 0; stream < 2; stream++) {
                AudioObjectID object = stream ? kObjectID_Stream_Output : kObjectID_Stream_Input;
                AudioStreamRangedDescription formats[13];
                assert(get(object, kAudioStreamPropertyAvailablePhysicalFormats,
                           kAudioObjectPropertyScopeGlobal, sizeof(formats), &written, formats) == noErr);
                assert(written == sizeof(formats));
                assert(formats[i].mFormat.mSampleRate == expected[i]);
                assert(formats[i].mFormat.mChannelsPerFrame == 2);
                assert(formats[i].mFormat.mBitsPerChannel == 32);
                assert(formats[i].mFormat.mBytesPerFrame == 8);
                assert(formats[i].mFormat.mFormatID == kAudioFormatLinearPCM);
                assert(formats[i].mFormat.mFormatFlags ==
                       (kAudioFormatFlagIsFloat | kAudioFormatFlagsNativeEndian | kAudioFormatFlagIsPacked));
            }
        }
        assert(!is_valid_sample_rate(22050) && !is_valid_sample_rate(0));
        puts("formats: PASS (13 ordered rates, stereo Float32, initial 48000)");
        return 0;
    }
    fprintf(stderr, "unknown test: %s\n", argv[1]);
    return 2;
}
