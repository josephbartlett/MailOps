# MailOps presentation assets

- [social-preview.svg](social-preview.svg): editable source, with live text and vector shapes.
- [social-preview.png](social-preview.png): the 1280 × 640 image for the repository's social preview. Keep it below 1 MB.

The artwork is a product graphic, not a screenshot. It describes the supported Proton Mail Bridge workflow and the actual MailOps operator loop. It contains no mailbox data or customer identities. Fonts are Segoe UI with Arial and generic sans-serif fallbacks; use Segoe UI when matching the checked-in PNG. No external images or fonts are embedded.

## Regenerate

Use a Node runtime with [Sharp](https://sharp.pixelplumbing.com/) available. Sharp is an artwork tool; it is not a MailOps application dependency. From the repository root:

```javascript
const sharp = require("sharp");

sharp("docs/assets/social-preview.svg", { density: 72 })
  .resize(1280, 640)
  .png({ compressionLevel: 9, palette: true, colours: 256, dither: 0 })
  .toFile("docs/assets/social-preview.png")
  .then(info => {
    if (info.width !== 1280 || info.height !== 640 || info.size >= 1000000) {
      throw new Error("Social preview must be 1280 × 640 and below 1 MB.");
    }
    console.log(info);
  })
  .catch(error => {
    console.error(error.message);
    process.exitCode = 1;
  });
```

Save the snippet as a temporary `.cjs` file in a tooling environment that has Sharp, then run it with Node while keeping the working directory at the MailOps repository root. An existing bundled Codex Node/Sharp runtime also works; no package changes are required in this repository.

Open the resulting PNG and check every label, the envelope graphic, spacing, and contrast at full size and thumbnail size. Confirm that it remains 1280 × 640 and below 1 MB before uploading it through the repository's social-preview setting. Artwork changes do not upload or publish themselves.
