# Foundations voiceover — recovered Anas recordings

The first scene uses 17 Arabic narration clips from the approved narration table. The existing recordings were downloaded from ElevenLabs Text to Speech History on 21 September 2026. This integration uses the recovered audio bytes without regeneration, conversion, or removal of their embedded provenance metadata.

- Integration branch: `foundations-merge`.
- Scene: `Assets/VR_LearningHub_Foundations_Working.unity`.
- Audio folder: `Assets/_GeometryVR/Audio/VoiceOver/Foundations/`.
- Voice: Anas (`R6nda3uM038xEEKi7GFl`), Eleven Multilingual v2.
- Audio stream: mono MP3, 44.1 kHz, 128 kbps. File sizes also include embedded metadata.
- Total duration: 106.74 seconds.
- Event mapping, Unity GUIDs, durations, byte sizes and SHA256 checksums: `Tools/foundations_voiceover_manifest.json`.

The original welcome recording from `2026-09-21T09:56:53` is used (14.52 seconds). The later welcome recording is also uploaded as `VO_FND_01_Welcome_Alternate_AR.mp3` (15.05 seconds); it remains unbound. The recovered set contains 18 MP3 files, with 17 primary narration bindings. All 17 clip GUIDs and the Foundations folder GUID are retained from the prior integration work.

The user-uploaded `success_toolMatch_b.mp3` adds one completion celebration (3.912 seconds, stereo, 24 kHz). Its original bytes are unchanged. The folder now contains 19 MP3 files: 17 bound narration clips, one bound celebration, and the unbound welcome alternate. The celebration has its own Unity metadata and is included in the manifest's `effects` list.

The application plays imported local audio. It needs no ElevenLabs API key or network call at runtime.

## Scene event mapping

The scene controller uses the following explicit audio fields. The prompts preserve the approved pronunciation spellings and English button labels.

| Clip | File | Controller field | Event | Duration |
|---|---|---|---|---:|
| 01 | `VO_FND_01_Welcome_AR.mp3` | `welcomeClip` | stage entry or new attempt | 14.52 s |
| 02 | `VO_FND_02_SelectCube_AR.mp3` | `selectCubeClip` | begin cube task | 4.78 s |
| 03 | `VO_FND_03_CubeFace_AR.mp3` | `cubeFaceClip` | correct cube grab | 6.35 s |
| 04 | `VO_FND_04_CubeEdge_AR.mp3` | `cubeEdgeClip` | cube face accepted | 5.09 s |
| 05 | `VO_FND_05_CubeVertex_AR.mp3` | `cubeVertexClip` | cube edge accepted | 4.55 s |
| 06 | `VO_FND_06_PlaceCube_AR.mp3` | `placeCubeClip` | cube vertex accepted, docking still required | 5.38 s |
| 07 | `VO_FND_07_SelectCylinder_AR.mp3` | `selectCylinderClip` | begin cylinder task | 5.33 s |
| 08 | `VO_FND_08_FirstBase_AR.mp3` | `firstBaseClip` | correct cylinder grab | 4.86 s |
| 09 | `VO_FND_09_SecondBase_AR.mp3` | `secondBaseClip` | first distinct base accepted | 4.36 s |
| 10 | `VO_FND_10_BaseAlreadySelected_AR.mp3` | `baseAlreadySelectedClip` | same cylinder base repeated | 5.43 s |
| 11 | `VO_FND_11_PlaceCylinder_AR.mp3` | `placeCylinderClip` | second distinct base accepted, docking still required | 6.40 s |
| 12 | `VO_FND_12_SelectSphere_AR.mp3` | `selectSphereClip` | begin sphere task | 4.08 s |
| 13 | `VO_FND_13_PlaceSphere_AR.mp3` | `placeSphereClip` | correct sphere grab, docking still required | 5.75 s |
| 14 | `VO_FND_14_AllTasksComplete_AR.mp3` | `allTasksCompleteClip` | after the celebration, once per attempt | 10.76 s |
| 15 | `VO_FND_15_WrongFeature_AR.mp3` | `wrongFeatureClip` | wrong property or wrong solid | 4.83 s |
| 16 | `VO_FND_16_WrongSocket_AR.mp3` | `wrongSocketClip` | wrong socket trigger | 5.46 s |
| 17 | `VO_FND_17_Help_AR.mp3` | `helpClip` | help requested | 8.80 s |
| Celebration | `success_toolMatch_b.mp3` | `completionCelebrationClip` | 3/3 first appears in an attempt | 3.912 s |

## Playback and validation

Narration follows accepted interaction events. A new instruction replaces the previous clip through the Foundations media coordinator. Video playback, leaving the stage, and resetting cancel current or deferred narration. A new attempt restarts the welcome; resetting unfinished objects resumes the current task instruction. Repeated automatic error prompts are throttled and cannot interrupt Help, the celebration, or the completion message. Help responds immediately to an explicit button press; pressing it again while its clip is playing does not restart it.

At the first completion of all three tasks, the controller refreshes the 3/3 display and plays the celebration once. The media coordinator waits for playback to finish before starting the existing congratulatory message on the same non-looping AudioSource. It does not use a fixed duration or a second overlapping source. AudioListener pause also pauses this wait. If the celebration reference is missing, the existing congratulatory message still plays.

The learner may select `Enter Transformations lab` at any time after completion. Stage navigation stops the current clip and cancels the queued message before switching stages. Help, video playback, a mode change, resetting objects, and a new attempt also cancel the sequence. Refreshing the UI, removing and re-docking a completed solid, or returning to the completed stage does not replay it. Starting a new attempt allows one new celebration after earning 3/3 again.

The repository validator checks all 19 audio checksums and Unity GUIDs, the 17 narration references plus the celebration reference, and the unused alternate. These are static checks; they do not prove Unity compilation or live playback. Unity import and headset playback still require the following check in the project:

1. Select `foundations-merge` in GitHub Desktop, pull its changes and allow Unity to import the audio.
2. Open the working scene and run `Geometry VR > Foundations > Validate Open Scene`.
3. Check the welcome, cube face/edge/vertex instructions and docking, both distinct cylinder bases and the repeated-base prompt, then sphere docking. At 3/3, hear the celebration once, followed by the existing congratulatory message without overlap. Remove and re-dock a completed solid; neither clip should restart.
4. Check a wrong socket, Help, New attempt, and resetting unfinished objects.
5. Leave for Transformations once during the celebration and once during the congratulatory message (use a new attempt for each check). Confirm immediate silence from Foundations and no delayed message in the next lab. Return to the completed stage; the celebration must not replay.
6. Start a tutorial video, request Help, or start a new attempt during the celebration. Confirm the pending congratulatory message is cancelled. Complete a new attempt to verify that one new celebration is allowed.

Run the static validators from the project root (Python with PyYAML):

```sh
python3 Tools/validate_foundations.py
python3 Tools/validate_foundations_voiceover.py
```

For a check of recovered files and their metadata before scene integration is available:

```sh
python3 Tools/validate_foundations_voiceover.py --audio-only
```
