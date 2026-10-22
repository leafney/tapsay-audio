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

static void plugin_properties(void) {
    unsigned cases = 0;
    for (unsigned acquired = 0; acquired < 2; acquired++) {
        gBox_Acquired = acquired;
        AudioObjectPropertyAddress address = {kAudioObjectPropertyOwnedObjects,
            kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
        UInt32 size = 0;
        assert((*gAudioServerPlugInDriverRef)->GetPropertyDataSize(gAudioServerPlugInDriverRef,
            kObjectID_PlugIn, 0, &address, 0, NULL, &size) == noErr);
        assert(size == (acquired ? 2 : 1) * sizeof(AudioObjectID));
        for (UInt32 capacity = 0; capacity <= 20; capacity++) {
            AudioObjectID ids[8];
            memset(ids, 0xa5, sizeof(ids));
            UInt32 written = 0;
            assert(get(kObjectID_PlugIn, address.mSelector, address.mScope,
                capacity, &written, &ids[1]) == noErr);
            UInt32 count = minimum(capacity / sizeof(AudioObjectID), acquired ? 2 : 1);
            assert(written == count * sizeof(AudioObjectID));
            if (count > 0) assert(ids[1] == kObjectID_Box);
            if (count > 1) assert(ids[2] == kObjectID_Device);
            for (unsigned i = 0; i < 8; i++) {
                if (i < 1 || i >= 1 + count) assert(ids[i] == 0xa5a5a5a5);
            }
            cases++;
        }
    }
    const AudioObjectPropertySelector selectors[] = {
        kAudioPlugInPropertyTranslateUIDToBox, kAudioPlugInPropertyTranslateUIDToDevice};
    CFStringRef values[] = {get_box_uid(), get_device_uid(), get_device2_uid(), CFSTR("unknown.uid")};
    for (unsigned selector = 0; selector < 2; selector++) {
        AudioObjectPropertyAddress address = {selectors[selector],
            kAudioObjectPropertyScopeGlobal, kAudioObjectPropertyElementMain};
        for (unsigned uid = 0; uid < 4; uid++) {
            for (UInt32 capacity = 0; capacity <= 12; capacity++) {
                AudioObjectID ids[3] = {0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5};
                UInt32 written = 0;
                OSStatus status = (*gAudioServerPlugInDriverRef)->GetPropertyData(
                    gAudioServerPlugInDriverRef, kObjectID_PlugIn, 0, &address,
                    sizeof(CFStringRef), &values[uid], capacity, &written, &ids[1]);
                if (capacity < sizeof(AudioObjectID)) {
                    assert(status == kAudioHardwareBadPropertySizeError);
                    assert(ids[1] == 0xa5a5a5a5);
                } else {
                    assert(status == noErr && written == sizeof(AudioObjectID));
                    AudioObjectID expected = kAudioObjectUnknown;
                    if (selector == 0 && uid == 0) expected = kObjectID_Box;
                    if (selector == 1 && uid == 1) expected = kObjectID_Device;
                    if (selector == 1 && uid == 2) expected = kObjectID_Device2;
                    assert(ids[1] == expected);
                }
                assert(ids[0] == 0xa5a5a5a5 && ids[2] == 0xa5a5a5a5);
                cases++;
            }
        }
        const UInt32 invalidSizes[] = {0, 1, sizeof(CFStringRef) - 1, sizeof(CFStringRef) + 1, 128};
        for (unsigned i = 0; i < 5; i++) {
            AudioObjectID id = 0xa5a5a5a5;
            UInt32 written = 0;
            assert((*gAudioServerPlugInDriverRef)->GetPropertyData(gAudioServerPlugInDriverRef,
                kObjectID_PlugIn, 0, &address, invalidSizes[i], &values[0], sizeof(id),
                &written, &id) == kAudioHardwareBadPropertySizeError);
            assert(id == 0xa5a5a5a5);
            cases++;
        }
        AudioObjectID id = 0xa5a5a5a5;
        UInt32 written = 0;
        assert((*gAudioServerPlugInDriverRef)->GetPropertyData(gAudioServerPlugInDriverRef,
            kObjectID_PlugIn, 0, &address, sizeof(CFStringRef), NULL, sizeof(id),
            &written, &id) == kAudioHardwareBadPropertySizeError);
        assert(id == 0xa5a5a5a5);
        cases++;
    }
    for (unsigned i = 0; i < 3; i++) CFRelease(values[i]);
    printf("plugin-properties: PASS (%u cases)\n", cases);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (strcmp(argv[1], "plugin-properties") == 0) {
        plugin_properties();
        return 0;
    }
    if (strcmp(argv[1], "control-matrix") == 0) {
        const AudioObjectID objects[] = {kObjectID_Device, kObjectID_Device2};
        const AudioObjectPropertyScope scopes[] = {kAudioObjectPropertyScopeGlobal,
            kAudioObjectPropertyScopeInput, kAudioObjectPropertyScopeOutput, 'test'};
        unsigned cases = 0;
        for (unsigned sizeEnabled = 0; sizeEnabled < 2; sizeEnabled++) {
            for (unsigned readEnabled = 0; readEnabled < 2; readEnabled++) {
                for (unsigned device = 0; device < 2; device++) {
                    for (unsigned scope = 0; scope < 4; scope++) {
                        AudioObjectPropertyAddress address = {kAudioObjectPropertyControlList,
                            scopes[scope], kAudioObjectPropertyElementMain};
                        UInt32 size = 0;
                        assert((*gAudioServerPlugInDriverRef)->PerformDeviceConfigurationChange(
                            gAudioServerPlugInDriverRef, kObjectID_Device,
                            sizeEnabled ? ChangeAction_EnablePitchControl : ChangeAction_DisablePitchControl,
                            NULL) == noErr);
                        assert((*gAudioServerPlugInDriverRef)->GetPropertyDataSize(
                            gAudioServerPlugInDriverRef, objects[device], 0, &address,
                            0, NULL, &size) == noErr);
                        UInt32 sizeCount = scope == 3 ? 0 : (scope == 0 ? 4 : 2);
                        if (device == 0 && scope == 0) sizeCount++;
                        if (device == 0 && (scope == 0 || scope == 2) && sizeEnabled) sizeCount++;
                        assert(size == sizeCount * sizeof(AudioObjectID));
                        // HAL may change enabled controls between size and data queries.
                        assert((*gAudioServerPlugInDriverRef)->PerformDeviceConfigurationChange(
                            gAudioServerPlugInDriverRef, kObjectID_Device,
                            readEnabled ? ChangeAction_EnablePitchControl : ChangeAction_DisablePitchControl,
                            NULL) == noErr);
                        AudioObjectID expected[6];
                        unsigned count = 0;
                        if (scope == 0 || scope == 1) {
                            expected[count++] = kObjectID_Volume_Input_Master;
                            expected[count++] = kObjectID_Mute_Input_Master;
                        }
                        if (scope == 0 || scope == 2) {
                            expected[count++] = kObjectID_Volume_Output_Master;
                            expected[count++] = kObjectID_Mute_Output_Master;
                            if (readEnabled && device == 0) expected[count++] = kObjectID_Pitch_Adjust;
                        }
                        if (scope == 0 && device == 0) expected[count++] = kObjectID_ClockSource;
                        // Every byte capacity includes partial IDs, exact and oversized buffers.
                        for (UInt32 capacity = 0; capacity <= 40; capacity++) {
                            AudioObjectID ids[16];
                            for (unsigned i = 0; i < 16; i++) ids[i] = 0xa55aa55a;
                            UInt32 written = 0;
                            assert(get(objects[device], address.mSelector, address.mScope,
                                       capacity, &written, &ids[1]) == noErr);
                            UInt32 returned = capacity / sizeof(AudioObjectID);
                            if (returned > count) returned = count;
                            assert(written == returned * sizeof(AudioObjectID));
                            for (unsigned i = 0; i < returned; i++) assert(ids[i + 1] == expected[i]);
                            assert(ids[0] == 0xa55aa55a);
                            for (unsigned i = returned + 1; i < 16; i++) assert(ids[i] == 0xa55aa55a);
                            cases++;
                        }
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
