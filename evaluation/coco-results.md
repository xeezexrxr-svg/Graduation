# COCO benchmark: all 80 YOLO26 object types

310 COCO validation photos (not used to train any of the models), chosen so every type appears at least 10 times. Created by `evaluation/coco_benchmark.py`.

## Strict scoring (only COCO's own names count)

| Set-up | Closest object named correctly | Objects found (recall) | Detections really there (precision) |
|---|---|---|---|
| combined | 61% (190/310) | 42% | 81% |
| everyday | 22% (69/310) | 30% | 69% |
| yolo26 | 69% (214/310) | 44% | 78% |

## Fairer scoring (clear equivalents accepted)

Also accepts more specific names that are still right: mug → cup, glass → cup, water bottle → bottle, shampoo bottle → bottle, medicine bottle → bottle, pill bottle → bottle, monitor → tv, desk → table, notebook → book, bag → handbag, plastic bag → handbag.

| Set-up | Closest object named correctly | Objects found (recall) | Detections really there (precision) |
|---|---|---|---|
| combined | 63% (194/310) | 42% | 80% |
| everyday | 24% (74/310) | 31% | 68% |
| yolo26 | 69% (214/310) | 44% | 78% |

Why the closest object was missed (fairer scoring):

| Set-up | Named another COCO type | Named something COCO doesn't label | Found nothing |
|---|---|---|---|
| combined | 59 | 42 | 15 |
| everyday | 78 | 79 | 79 |
| yolo26 | 60 | 0 | 36 |

## Per object type

Found = real objects of this type found and named correctly. Correct = detections with this name that were really there. ✗ = the type isn't in vocabulary.txt, so the everyday model can't name it.

| Object | Real | Found: combined | everyday | yolo26 | Correct: combined | everyday | yolo26 |
|---|---|---|---|---|---|---|---|
| airplane ✗ | 11 | 73% | 0% | 73% | 100% | – | 89% |
| apple | 14 | 7% | 14% | 7% | 25% | 25% | 25% |
| backpack | 18 | 6% | 6% | 6% | 50% | 100% | 50% |
| ball | 36 | 28% | 3% | 31% | 91% | 33% | 79% |
| banana | 15 | 13% | 13% | 13% | 50% | 22% | 50% |
| baseball bat ✗ | 14 | 36% | 0% | 36% | 83% | – | 71% |
| baseball glove ✗ | 10 | 30% | 0% | 30% | 100% | – | 100% |
| bear ✗ | 10 | 70% | 0% | 70% | 100% | – | 100% |
| bed | 11 | 45% | 55% | 64% | 56% | 60% | 78% |
| bench ✗ | 33 | 6% | 0% | 6% | 50% | – | 50% |
| bicycle | 18 | 44% | 33% | 50% | 89% | 86% | 75% |
| bird | 20 | 80% | 10% | 80% | 94% | 100% | 89% |
| boat ✗ | 12 | 25% | 0% | 25% | 100% | – | 100% |
| book | 55 | 13% | 5% | 13% | 88% | 75% | 88% |
| bottle | 61 | 36% | 31% | 38% | 71% | 53% | 72% |
| bowl | 46 | 30% | 37% | 52% | 67% | 71% | 69% |
| broccoli | 11 | 55% | 45% | 64% | 100% | 71% | 88% |
| bus | 11 | 73% | 91% | 73% | 100% | 53% | 100% |
| cake | 26 | 12% | 8% | 15% | 50% | 33% | 50% |
| car | 83 | 53% | 31% | 54% | 79% | 96% | 76% |
| carrot | 16 | 6% | 0% | 12% | 12% | 0% | 20% |
| cat | 10 | 70% | 70% | 70% | 47% | 64% | 47% |
| cell phone | 27 | 7% | 15% | 7% | 67% | 44% | 50% |
| chair | 125 | 28% | 25% | 29% | 65% | 72% | 62% |
| clock | 17 | 41% | 29% | 47% | 70% | 36% | 80% |
| computer mouse | 11 | 45% | 36% | 64% | 100% | 100% | 100% |
| cow ✗ | 21 | 48% | 0% | 48% | 100% | – | 100% |
| cup | 56 | 36% | 36% | 38% | 67% | 61% | 64% |
| dog | 13 | 54% | 62% | 62% | 100% | 50% | 89% |
| doughnut | 32 | 16% | 0% | 16% | 100% | – | 100% |
| elephant ✗ | 14 | 64% | 0% | 64% | 75% | – | 53% |
| fire hydrant ✗ | 10 | 40% | 0% | 40% | 67% | – | 67% |
| fork | 12 | 33% | 25% | 42% | 80% | 100% | 62% |
| frisbee ✗ | 10 | 70% | 0% | 70% | 88% | – | 88% |
| giraffe ✗ | 11 | 91% | 0% | 91% | 100% | – | 100% |
| hair dryer ✗ | 10 | 0% | 0% | 0% | – | – | – |
| handbag | 25 | 4% | 16% | 4% | 100% | 33% | 100% |
| horse ✗ | 12 | 50% | 0% | 50% | 75% | – | 75% |
| hot dog | 10 | 40% | 10% | 40% | 100% | 33% | 80% |
| keyboard | 14 | 57% | 57% | 57% | 67% | 73% | 67% |
| kite ✗ | 12 | 92% | 0% | 92% | 100% | – | 100% |
| knife | 26 | 15% | 8% | 19% | 100% | 33% | 100% |
| laptop | 14 | 71% | 57% | 71% | 83% | 80% | 83% |
| microwave | 15 | 73% | 60% | 73% | 92% | 69% | 85% |
| motorcycle | 10 | 50% | 50% | 50% | 83% | 71% | 83% |
| orange | 24 | 25% | 21% | 25% | 50% | 20% | 50% |
| oven | 20 | 55% | 25% | 55% | 92% | 36% | 92% |
| parking meter ✗ | 11 | 18% | 0% | 18% | 100% | – | 67% |
| person | 609 | 60% | 59% | 61% | 88% | 76% | 87% |
| pizza | 20 | 30% | 25% | 30% | 100% | 83% | 100% |
| potted plant | 25 | 24% | 16% | 24% | 50% | 80% | 50% |
| refrigerator | 16 | 69% | 62% | 69% | 85% | 77% | 85% |
| remote control | 11 | 18% | 0% | 36% | 50% | – | 50% |
| sandwich | 11 | 18% | 9% | 73% | 100% | 100% | 80% |
| scissors | 11 | 18% | 9% | 18% | 100% | 50% | 67% |
| sheep ✗ | 10 | 50% | 0% | 50% | 83% | – | 83% |
| sink | 26 | 50% | 50% | 50% | 81% | 87% | 81% |
| skateboard ✗ | 10 | 100% | 0% | 100% | 91% | – | 91% |
| skis ✗ | 20 | 15% | 0% | 15% | 100% | – | 100% |
| snowboard ✗ | 11 | 27% | 0% | 27% | 60% | – | 60% |
| sofa | 19 | 21% | 16% | 21% | 80% | 60% | 57% |
| spoon | 30 | 13% | 10% | 13% | 80% | 50% | 67% |
| stop sign ✗ | 10 | 70% | 0% | 70% | 100% | – | 100% |
| suitcase ✗ | 13 | 15% | 0% | 23% | 67% | – | 75% |
| surfboard ✗ | 14 | 0% | 0% | 0% | – | – | – |
| table | 48 | 25% | 6% | 46% | 67% | 50% | 73% |
| teddy bear | 13 | 62% | 62% | 77% | 89% | 67% | 91% |
| tennis racket ✗ | 11 | 73% | 0% | 73% | 89% | – | 89% |
| tie ✗ | 10 | 30% | 0% | 30% | 100% | – | 100% |
| toaster | 9 | 22% | 56% | 22% | 100% | 83% | 100% |
| toilet | 16 | 56% | 25% | 56% | 82% | 80% | 82% |
| toothbrush | 14 | 0% | 0% | 0% | 0% | – | 0% |
| traffic light ✗ | 26 | 31% | 0% | 31% | 80% | – | 67% |
| train ✗ | 10 | 80% | 0% | 80% | 73% | – | 67% |
| truck ✗ | 22 | 27% | 0% | 36% | 60% | – | 67% |
| tv | 30 | 63% | 70% | 63% | 90% | 88% | 86% |
| umbrella | 14 | 29% | 29% | 29% | 80% | 100% | 67% |
| vase | 41 | 20% | 20% | 24% | 73% | 67% | 67% |
| wine glass | 16 | 44% | 38% | 50% | 58% | 86% | 57% |
| zebra ✗ | 12 | 92% | 0% | 92% | 100% | – | 92% |
