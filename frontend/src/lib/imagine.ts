/** Latura avatarului salvat — mai mult nu se vede pe niciun ecran. */
const LATURA = 512;

/**
 * Taie poza patrat (din centru), o micsoreaza la 512x512 si o recomprima JPEG.
 *
 * Se ruleaza in browser inainte de upload: din 4-5 MB de la camera raman ~60 KB,
 * deci incarcarea e instant si nu atingem limita bucketului (0005_avatar_profil.sql).
 */
export async function pregatesteAvatar(sursa: Blob): Promise<File> {
  const bitmap = await createImageBitmap(sursa);

  try {
    const latura = Math.min(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = Math.min(latura, LATURA);

    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D indisponibil.");

    ctx.drawImage(
      bitmap,
      (bitmap.width - latura) / 2,
      (bitmap.height - latura) / 2,
      latura,
      latura,
      0,
      0,
      canvas.width,
      canvas.height,
    );

    const blob = await new Promise<Blob | null>((rezolva) =>
      canvas.toBlob(rezolva, "image/jpeg", 0.9),
    );

    if (!blob) throw new Error("Nu s-a putut genera poza.");

    return new File([blob], "avatar.jpg", { type: "image/jpeg" });
  } finally {
    bitmap.close();
  }
}

/** Latura maxima pentru poza buletinului — mai mare decat avatarul, ca OCR-ul sa aiba ce citi. */
const LATURA_DOCUMENT = 1600;

/**
 * Redimensioneaza poza buletinului fara sa o taie patrat (ar putea pierde
 * cifre din CNP) si o recomprima JPEG. Ruleaza in browser inainte de upload.
 */
export async function pregatesteDocument(sursa: Blob): Promise<File> {
  const bitmap = await createImageBitmap(sursa);

  try {
    const scala = Math.min(1, LATURA_DOCUMENT / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scala);
    canvas.height = Math.round(bitmap.height * scala);

    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D indisponibil.");

    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((rezolva) =>
      canvas.toBlob(rezolva, "image/jpeg", 0.92),
    );

    if (!blob) throw new Error("Nu s-a putut genera poza.");

    return new File([blob], "buletin.jpg", { type: "image/jpeg" });
  } finally {
    bitmap.close();
  }
}
