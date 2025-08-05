import asyncio
# from src.backend.llm.transcriber import Transcriber
# import sys
# import os

def merge_speaker_ranges(speaker_ranges):

    last_speaker = None
    previous_end = None
    last_start = None

    merged_speaker_ranges = []

    for entry in speaker_ranges:
        if previous_end is not None:
            if entry["speaker"] != last_speaker or entry["start_ms"] != previous_end:
                merged_speaker_ranges.append({"speaker": last_speaker, 
                                                "start_ms": last_start, 
                                                "end_ms": previous_end})
                last_start = entry["start_ms"]
                last_speaker = entry["speaker"]
        else:
            last_speaker = entry["speaker"]
            last_start = entry["start_ms"]
        previous_end = entry["end_ms"]

    merged_speaker_ranges.append({"speaker": last_speaker,
                                    "start_ms": last_start, 
                                    "end_ms": previous_end})

    return merged_speaker_ranges

async def main():
    print(merge_speaker_ranges([{'speaker': 'Софія Сампара', 'start_ms': 50420, 'end_ms': 50488}, {'speaker': 'Софія Сампара', 'start_ms': 50488, 'end_ms': 50549}, {'speaker': 'Софія', 'start_ms': 50549, 'end_ms': 50609}, {'speaker': 'Софія Сампара', 'start_ms': 50609, 'end_ms': 50672}, {'speaker': 'Софія Сампара', 'start_ms': 50672, 'end_ms': 50735}, {'speaker': 'Софія Сампара', 'start_ms': 50735, 'end_ms': 50797}, {'speaker': 'Софія Сампара', 'start_ms': 50797, 'end_ms': 50861}, {'speaker': 'Софія Сампара', 'start_ms': 50861, 'end_ms': 50922}, {'speaker': 'Софія Сампара', 'start_ms': 50922, 'end_ms': 50985}, {'speaker': 'Софія Сампара', 'start_ms': 50985, 'end_ms': 51075}, {'speaker': 'Софія Сампара', 'start_ms': 51075, 'end_ms': 51141}, {'speaker': 'Софія Сампара', 'start_ms': 51141, 'end_ms': 51201}, {'speaker': 'Софія Сампара', 'start_ms': 51201, 'end_ms': 51264}, {'speaker': 'Софія Сампара', 'start_ms': 51264, 'end_ms': 51326}, {'speaker': 'Софія Сампара', 'start_ms': 51326, 'end_ms': 51387}, {'speaker': 'Софія Сампара', 'start_ms': 51387, 'end_ms': 51448}, {'speaker': 'Софія Сампара', 'start_ms': 51448, 'end_ms': 51510}, {'speaker': 'Софія Сампара', 'start_ms': 51510, 'end_ms': 51572}, {'speaker': 'Софія Сампара', 'start_ms': 51572, 'end_ms': 51637}, {'speaker': 'Софія Сампара', 'start_ms': 51637, 'end_ms': 51696}, {'speaker': 'Софія Сампара', 'start_ms': 51696, 'end_ms': 51757}, {'speaker': 'Софія Сампара', 'start_ms': 53498, 'end_ms': 53559}, {'speaker': 'Софія Сампара', 'start_ms': 53559, 'end_ms': 53622}, {'speaker': 'Софія Сампара', 'start_ms': 53622, 'end_ms': 53683}, {'speaker': 'Софія Сампара', 'start_ms': 53683, 'end_ms': 53742}, {'speaker': 'Софія Сампара', 'start_ms': 53742, 'end_ms': 53807}, {'speaker': 'Софія Сампара', 'start_ms': 53807, 'end_ms': 53861}, {'speaker': 'Софія Сампара', 'start_ms': 53861, 'end_ms': 53917}, {'speaker': 'Софія Сампара', 'start_ms': 53917, 'end_ms': 53978}, {'speaker': 'Софія Сампара', 'start_ms': 53978, 'end_ms': 54041}, {'speaker': 'Софія Сампара', 'start_ms': 54041, 'end_ms': 54100}, {'speaker': 'Софія Сампара', 'start_ms': 54100, 'end_ms': 54165}, {'speaker': 'Софія Сампара', 'start_ms': 54165, 'end_ms': 54220}, {'speaker': 'Софія Сампара', 'start_ms': 56101, 'end_ms': 56162}, {'speaker': 'Софія Сампара', 'start_ms': 56162, 'end_ms': 56225}, {'speaker': 'Софія Сампара', 'start_ms': 56225, 'end_ms': 56288}, {'speaker': 'Софія Сампара', 'start_ms': 56288, 'end_ms': 56347}, {'speaker': 'Софія Сампара', 'start_ms': 56347, 'end_ms': 56410}, {'speaker': 'Софія Сампара', 'start_ms': 56410, 'end_ms': 56472}, {'speaker': 'Софія Сампара', 'start_ms': 56472, 'end_ms': 56533}, {'speaker': 'Софія Сампара', 'start_ms': 56533, 'end_ms': 56595}, {'speaker': 'Софія Сампара', 'start_ms': 56595, 'end_ms': 56657}, {'speaker': 'Софія Сампара', 'start_ms': 56657, 'end_ms': 56720}, {'speaker': 'Софія Сампара', 'start_ms': 56720, 'end_ms': 56783}, {'speaker': 'Софія Сампара', 'start_ms': 56783, 'end_ms': 56843}, {'speaker': 'Софія Сампара', 'start_ms': 56843, 'end_ms': 56905}, {'speaker': 'Софія Сампара', 'start_ms': 57029, 'end_ms': 57092}, {'speaker': 'Софія Сампара', 'start_ms': 57092, 'end_ms': 57155}, {'speaker': 'Софія Сампара', 'start_ms': 57155, 'end_ms': 57217}, {'speaker': 'Софія Сампара', 'start_ms': 57217, 'end_ms': 57278}, {'speaker': 'Софія Сампара', 'start_ms': 57278, 'end_ms': 57340}, {'speaker': 'Софія Сампара', 'start_ms': 57340, 'end_ms': 57404}, {'speaker': 'Софія Сампара', 'start_ms': 57404, 'end_ms': 57492}, {'speaker': 'Софія Сампара', 'start_ms': 57492, 'end_ms': 57558}, {'speaker': 'Софія Сампара', 'start_ms': 59740, 'end_ms': 59801}, {'speaker': 'Софія Сампара', 'start_ms': 59801, 'end_ms': 59861}, {'speaker': 'Софія Сампара', 'start_ms': 59861, 'end_ms': 59924}, {'speaker': 'Софія Сампара', 'start_ms': 59924, 'end_ms': 59980}, {'speaker': 'Софія Сампара', 'start_ms': 59980, 'end_ms': 60036}, {'speaker': 'Софія Сампара', 'start_ms': 60036, 'end_ms': 60097}, {'speaker': 'Софія Сампара', 'start_ms': 60097, 'end_ms': 60160}, {'speaker': 'Софія Сампара', 'start_ms': 60160, 'end_ms': 60220}, {'speaker': 'Софія Сампара', 'start_ms': 60220, 'end_ms': 60283}, {'speaker': 'Софія Сампара', 'start_ms': 60283, 'end_ms': 60350}, {'speaker': 'Софія Сампара', 'start_ms': 60350, 'end_ms': 60402}]))

if __name__ == "__main__":
    asyncio.run(main())
