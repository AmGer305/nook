# nook

The mailbox for a Kindle that lives in a coffee nook.

Every morning the Kindle reads `cards.txt` on this branch and downloads any card it does not have yet
from the `cards` folder. Cards that are no longer listed are set aside on the Kindle.

## How it works

- `cards.txt` lists the cards, one file name per line. This list is what the Kindle goes by.
- `cards/` holds the pictures: 1072 x 1448 pixels, greyscale PNG.
- The Kindle shows the cards in name order, so the number at the front of each name sets the sequence.
- To change a card, give the new version a new name (for example `03b-...`) and update `cards.txt`.
  A file that keeps its name is not downloaded again.

Nothing here runs on the Kindle. It only ever fetches pictures and this list.

The sentences on the cards are old enough to be in the public domain. The notes under them were
written for this Kindle.
