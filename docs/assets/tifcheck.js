/* GEMSDOE52 - browser-side pre-submission validator for the DOE GEMS competition GeoTIFF.
 *
 * Why this exists: the organiser's submission form rejects a file with
 *   "Predicted values must be in range [0, 1]"
 * and gives no other detail. This script decodes the actual pixels of a downloaded .tif (or a .zip
 * containing exactly one .tif) entirely in the browser - nothing is uploaded anywhere - and reports
 * every rule from the official problem page as an explicit PASS/FAIL, so the answer to
 * "is it OK to submit this file?" is visible before a weekly slot is spent.
 *
 * Official rules checked (source: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/,
 * fetched 2026-10-09):
 *   - single layer, 32-bit float, values between 0 and 1
 *   - same projected CRS as the training data: UTM zone 11N, EPSG:32611
 *   - same resolution as the training data: 100 m
 *   - same bounds as the training data; data outside the bounds is null or nan
 *   - a single-band GeoTIFF (.tif), or a .zip containing a single GeoTIFF (submission-form text)
 *
 * Reference geometry below is MEASURED from data/sample_submission.tif by scripts/publish_h82_site.py
 * and injected as window.GEMS_REF; the defaults here are that same measurement, kept so the file is
 * usable standalone. Nothing is asserted that was not read off the organiser's own template.
 *
 * Supports: TIFF little/big endian, strips and 256 px tiles, compression none(1) / LZW(5) /
 * deflate-zlib(8), horizontal-differencing predictor(317=2), float32 (BitsPerSample 32, SampleFormat 3),
 * and .zip containers (store + raw-deflate).
 */
(function () {
  "use strict";

  var REF = (typeof window !== "undefined" && window.GEMS_REF) || {
    width: 3292, height: 3730, epsg: 32611,
    pixelScale: [100.0, 100.0, 0.0],
    tiepoint: [0.0, 0.0, 0.0, 243350.0, 4508550.0, 0.0],
    bitsPerSample: 32, sampleFormat: 3, samplesPerPixel: 1,
    vMin: 0.0, vMax: 1.0
  };

  // ------------------------------------------------------------------ byte readers
  function Reader(buf, little) {
    this.v = new DataView(buf); this.o = 0; this.little = !!little;
  }
  Reader.prototype.u8 = function () { return this.v.getUint8(this.o++); };
  Reader.prototype.u16 = function () { var x = this.v.getUint16(this.o, this.little); this.o += 2; return x; };
  Reader.prototype.u32 = function () { var x = this.v.getUint32(this.o, this.little); this.o += 4; return x; };
  Reader.prototype.f64 = function () { var x = this.v.getFloat64(this.o, this.little); this.o += 8; return x; };

  // Absolute-offset reader over the WHOLE buffer: slicing here silently shifted every IFD value
  // field by the IFD offset (found by testing against real files, not by reading the code).
  function at(buf, off, little) { var r = new Reader(buf, little); r.o = off; return r; }

  // ------------------------------------------------------------------ inflate helpers
  function inflate(bytes, raw) {
    var fmt = raw ? "deflate-raw" : "deflate";
    if (typeof DecompressionStream === "undefined") {
      throw new Error("this browser has no DecompressionStream; use Chrome/Edge/Firefox 113+/Safari 16.4+");
    }
    var ds = new DecompressionStream(fmt);
    var stream = new Blob([bytes]).stream().pipeThrough(ds);
    return new Response(stream).arrayBuffer();
  }

  // ------------------------------------------------------------------ TIFF LZW
  // Empirically settled on this repository's own files: GDAL/libtiff-written TIFF LZW here uses the
  // EARLY-change width rule (grow the code width when next+1 reaches 2^bits). delta=1 decoded all
  // 3,730 strips of data/sample_submission.tif to exactly 13,168 bytes; delta=0 decoded 3. Both are
  // tried per block and only an exact-length match is accepted, so a mis-decode can never silently
  // produce plausible-looking pixels.
  function lzwRun(bytes, expected, delta) {
    var out = [], dict = [], next = 258, bits = 9, prev = -1, acc = 0, nb = 0, i;
    for (i = 0; i < 256; i++) dict[i] = [i];
    for (i = 0; i < bytes.length; i++) {
      acc = ((acc << 8) | bytes[i]) >>> 0; nb += 8;
      while (nb >= bits) {
        nb -= bits;
        var code = (acc >>> nb) & ((1 << bits) - 1);
        if (code === 256) { next = 258; bits = 9; prev = -1; continue; }
        if (code === 257) { return out.length === expected ? out : null; }
        var e;
        if (code < next && dict[code]) e = dict[code];
        else if (code === next && prev >= 0) e = dict[prev].concat([dict[prev][0]]);
        else return null;
        for (var k = 0; k < e.length; k++) out.push(e[k]);
        if (prev >= 0) {
          dict[next++] = dict[prev].concat([e[0]]);
          while (next + delta >= (1 << bits) && bits < 12) bits++;
        }
        prev = code;
      }
    }
    return out.length === expected ? out : null;
  }

  function lzwDecode(bytes, expected) {
    var r = lzwRun(bytes, expected, 1);          // early change (what GDAL wrote here)
    if (r) return r;
    r = lzwRun(bytes, expected, 0);              // late change (TIFF 6.0 T.42 erratum)
    if (r) return r;
    throw new Error("LZW decode did not reproduce the expected block length (" + expected +
      " bytes); refusing to guess at pixel values");
  }

  // ------------------------------------------------------------------ predictor undo
  function undoPredictor(u8, bytesPerRow, stride, elemSize) {
    // TIFF PREDICTOR=2 horizontal differencing. The addition is performed on ELEMENTS of
    // elemSize = BitsPerSample/8 bytes, with carry propagating inside each element - libtiff's
    // horAcc8/16/32/64. Doing it byte-wise instead silently corrupts float32 (verified: byte-wise
    // left 2,412,363 of 12,279,160 pixels wrong on docs/downloads/h75-candidate.tif, element-wise
    // reproduced all 12,241,506 zeros and all 37,654 ones exactly). Rows are handled separately:
    // each scanline of the block restarts the accumulation.
    var dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    var get, set, mask;
    if (elemSize === 1) { get = function (o) { return dv.getUint8(o); }; set = function (o, x) { dv.setUint8(o, x & 0xff); }; }
    else if (elemSize === 2) { get = function (o) { return dv.getUint16(o, true); }; set = function (o, x) { dv.setUint16(o, x & 0xffff, true); }; }
    else if (elemSize === 4) { get = function (o) { return dv.getUint32(o, true); }; set = function (o, x) { dv.setUint32(o, x >>> 0, true); }; }
    else throw new Error("PREDICTOR=2 with " + elemSize * 8 + "-bit samples is not supported here");
    for (var r = 0; r + bytesPerRow <= u8.length; r += bytesPerRow) {
      for (var i = stride; i < bytesPerRow; i += elemSize) {
        set(r + i, (get(r + i) + get(r + i - stride)) >>> 0);
      }
    }
    return u8;
  }

  // ------------------------------------------------------------------ IFD parsing
  var TYPE_SIZE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8 };

  function readValues(buf, little, type, count, valueOffsetRaw) {
    var size = TYPE_SIZE[type] || 1;
    var total = size * count;
    var off;
    if (total <= 4) {
      off = valueOffsetRaw;                       // inline: the 4 bytes of the value field
    } else {
      off = new DataView(buf).getUint32(valueOffsetRaw, little);
    }
    var r = at(buf, off, little);
    var out = [];
    for (var i = 0; i < count; i++) {
      if (type === 3) out.push(r.u16());
      else if (type === 4) out.push(r.u32());
      else if (type === 12) out.push(r.f64());
      else if (type === 11) { out.push(r.v.getFloat32(r.o, r.little)); r.o += 4; }
      else if (type === 5 || type === 10) { var n = r.u32(), d = r.u32(); out.push(d ? n / d : null); }
      else out.push(r.u8());
    }
    return out;
  }

  function parseIfd(buf, little, ifdOffset) {
    var r = at(buf, ifdOffset, little);
    var n = r.u16();
    var tags = {};
    for (var i = 0; i < n; i++) {
      var tag = r.u16(), type = r.u16(), count = r.u32();
      var rawOff = r.o; r.o += 4;
      try { tags[tag] = { type: type, count: count, values: readValues(buf, little, type, count, rawOff) }; }
      catch (e) { tags[tag] = { type: type, count: count, error: String(e) }; }
    }
    return tags;
  }

  function geoKeys(tags) {
    // GeoKeyDirectoryTag 34735: header(4) then (keyId, tiffTagLocation, count, valueOffset) triples.
    var out = {};
    if (!tags[34735] || !tags[34735].values) return out;
    var v = tags[34735].values;
    var n = v[3];
    for (var i = 0; i < n; i++) {
      var b = 4 + i * 4;
      if (b + 3 >= v.length) break;
      var keyId = v[b], loc = v[b + 1], cnt = v[b + 2], off = v[b + 3];
      if (loc === 0) out[keyId] = off;
    }
    return out;
  }

  // ------------------------------------------------------------------ ZIP
  async function unzipSingleTif(buf) {
    var u8 = new Uint8Array(buf);
    var i, eocd = -1;
    for (i = u8.length - 22; i >= Math.max(0, u8.length - 66000); i--) {
      if (u8[i] === 0x50 && u8[i + 1] === 0x4b && u8[i + 2] === 0x05 && u8[i + 3] === 0x06) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("not a ZIP file (no end-of-central-directory record)");
    var dv = new DataView(buf);
    var nEntries = dv.getUint16(eocd + 10, true);
    var cdOff = dv.getUint32(eocd + 16, true);
    var entries = [];
    var o = cdOff;
    for (i = 0; i < nEntries; i++) {
      if (dv.getUint32(o, true) !== 0x02014b50) throw new Error("corrupt ZIP central directory at " + o);
      // fixed 46-byte central-directory header; offsets per APPNOTE.TXT 4.3.12
      var method = dv.getUint16(o + 10, true);
      var csize = dv.getUint32(o + 20, true);
      var usize = dv.getUint32(o + 24, true);
      var nlen = dv.getUint16(o + 28, true);
      var elen = dv.getUint16(o + 30, true);
      var clen = dv.getUint16(o + 32, true);
      var lho = dv.getUint32(o + 42, true);
      var name = new TextDecoder().decode(u8.slice(o + 46, o + 46 + nlen));
      o += 46 + nlen + elen + clen;
      entries.push({ name: name, method: method, csize: csize, usize: usize, lho: lho });
    }
    var tifs = entries.filter(function (e) { return /\.tif?f?$/i.test(e.name); });
    if (tifs.length !== 1) {
      throw new Error("the ZIP must contain exactly ONE GeoTIFF; found " + tifs.length +
        " (" + entries.map(function (e) { return e.name; }).join(", ") + ")");
    }
    var e = tifs[0];
    var lr = new Reader(buf, true); lr.o = e.lho;
    if (lr.u32() !== 0x04034b50) throw new Error("corrupt ZIP local header");
    lr.o += 22;
    var lnlen = lr.u16(), lelen = lr.u16();
    var dataStart = e.lho + 30 + lnlen + lelen;
    var data = u8.slice(dataStart, dataStart + e.csize);
    var out;
    if (e.method === 0) out = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
    else if (e.method === 8) out = await inflate(data, true);
    else throw new Error("unsupported ZIP compression method " + e.method);
    if (out.byteLength !== e.usize) throw new Error("ZIP inflate size mismatch");
    return { entry: e.name, buffer: out, entries: entries.map(function (x) { return x.name; }) };
  }

  // ------------------------------------------------------------------ main check
  async function checkFile(file) {
    var t0 = Date.now();
    var buf = await file.arrayBuffer();
    var name = file.name, zipInfo = null;
    if (/\.zip$/i.test(name)) { zipInfo = await unzipSingleTif(buf); buf = zipInfo.buffer; name = zipInfo.entry; }
    return await checkTiff(buf, name, file.size, zipInfo, Date.now() - t0);
  }

  async function checkTiff(buf, name, diskBytes, zipInfo, ms) {
    var checks = [];
    function add(id, label, pass, got, want, note, severity) {
      checks.push({ id: id, label: label, pass: !!pass, got: got, want: want, note: note || "",
                    severity: severity || "hard" });
    }
    var head = new Uint8Array(buf.slice(0, 4));
    var little;
    if (head[0] === 0x49 && head[1] === 0x49) little = true;
    else if (head[0] === 0x4d && head[1] === 0x4d) little = false;
    else throw new Error("not a TIFF (no II/MM byte-order marker)");
    var r0 = new Reader(buf, little); r0.o = 2;
    var magic = r0.u16();
    if (magic !== 42) throw new Error("TIFF magic is " + magic + ", expected 42");
    r0.o = 4;
    var ifd0 = r0.u32();
    var t = parseIfd(buf, little, ifd0);
    function g(tag, dflt) { return (t[tag] && t[tag].values && t[tag].values.length) ? t[tag].values : dflt; }
    function g0(tag, dflt) { var v = g(tag, null); return v ? v[0] : dflt; }

    var width = g0(256, null), height = g0(257, null);
    var bps = g(258, []), spp = g0(277, 1), sf = g0(339, 1), comp = g0(259, 1), pred = g0(317, 1);
    var scale = g(33550, []), tie = g(33922, []);
    var gk = geoKeys(t);
    var epsg = gk[3072] != null ? gk[3072] : null;

    add("layers", "Single layer (SamplesPerPixel = 1)", spp === 1, spp, 1);
    add("bits", "32-bit pixels (BitsPerSample = 32)", bps.length === 1 && bps[0] === 32, bps.join(","), "32");
    add("float", "IEEE float (SampleFormat = 3)", sf === 3, sf, 3,
      "1=int, 2=uint, 3=IEEE float. The official spec requires 32-bit float.");
    add("shape", "Grid shape = " + REF.height + " rows x " + REF.width + " cols",
      height === REF.height && width === REF.width, height + " x " + width, REF.height + " x " + REF.width);
    add("crs", "Projected CRS = EPSG:" + REF.epsg + " (UTM zone 11N)", epsg === REF.epsg, epsg, REF.epsg,
      "Read from GeoKeyDirectoryTag 3072 (ProjectedCSTypeGeoKey).");
    add("scale", "Resolution = 100 m x 100 m",
      scale.length >= 2 && Math.abs(scale[0] - REF.pixelScale[0]) < 1e-6 && Math.abs(scale[1] - REF.pixelScale[1]) < 1e-6,
      scale.slice(0, 3).join(", "), REF.pixelScale.join(", "), "ModelPixelScaleTag 33550.");
    add("origin", "Origin (tiepoint) = " + REF.tiepoint[3] + " E, " + REF.tiepoint[4] + " N",
      tie.length >= 6 && Math.abs(tie[3] - REF.tiepoint[3]) < 1e-3 && Math.abs(tie[4] - REF.tiepoint[4]) < 1e-3,
      tie.length >= 6 ? tie[3] + ", " + tie[4] : "(missing)", REF.tiepoint[3] + ", " + REF.tiepoint[4],
      "ModelTiepointTag 33922; bounds follow as origin +/- size*scale.");

    // ---------------- pixel decode
    // Only 32-bit IEEE float single-layer pixels are decoded. Reading any other sample type as
    // float32 would produce plausible-looking but meaningless statistics (verified: a float64 copy
    // of a good file reported "max 1.875, 18,403 above 1" when the true values were 0 and 1), and a
    // misleading number is worse than no number. The format rows above already fail in that case.
    var decodable = (spp === 1 && bps.length === 1 && bps[0] === 32 && sf === 3);
    if (!decodable) {
      add("decode", "Pixel values decoded and scanned", false,
        "skipped: this file is not single-layer 32-bit IEEE float",
        "single-layer float32",
        "Fix the data type first; the value-range rule cannot be evaluated on a raster whose sample " +
        "type is not the one the organiser specifies.");
      var npass0 = checks.filter(function (c) { return c.severity === "hard" && c.pass; }).length;
      var hard0 = checks.filter(function (c) { return c.severity === "hard"; });
      return { file: name, diskBytes: diskBytes, zip: zipInfo, compression: comp, predictor: pred,
        tiled: !!(t[322] && t[323]), littleEndian: little, geoKeys: gk, checks: checks,
        stats: null, passed: npass0, total: hard0.length, ok: false, ms: ms,
        reference: REF, reference_class: "MEASURED from the organiser template data/sample_submission.tif, not assumed" };
    }
    var tiled = t[322] && t[323];
    var tw = tiled ? g0(322, 256) : width;
    var th = tiled ? g0(323, 256) : g0(278, height);
    var offsets = tiled ? g(324, []) : g(273, []);
    var counts = tiled ? g(325, []) : g(279, []);
    var nColsTiles = Math.ceil(width / tw), nRowsTiles = Math.ceil(height / th);
    var expectTiles = tiled ? nColsTiles * nRowsTiles : offsets.length;
    add("blocks", (tiled ? "Tiles" : "Strips") + " present: " + offsets.length + " of " + expectTiles,
      offsets.length === expectTiles && counts.length === expectTiles,
      offsets.length + "/" + counts.length, expectTiles + "/" + expectTiles);

    var bytesPerTileRow = tw * spp * (bps[0] / 8);
    var tileBytes = bytesPerTileRow * th;
    var stride = spp * (bps[0] / 8);

    var stats = { n: 0, nan: 0, inf: 0, neg: 0, gt1: 0, zero: 0, one: 0, finite: 0, nonzero: 0,
      min: Infinity, max: -Infinity, outOfRange: [], nanRow0: null, nanRow1: null, nanCol0: null, nanCol1: null };
    var decoded = new Uint8Array(width * height * 4);
    for (var b = 0; b < offsets.length; b++) {
      var raw = new Uint8Array(buf.slice(offsets[b], offsets[b] + counts[b]));
      var bytes;
      if (comp === 1) bytes = raw;
      else if (comp === 8) bytes = new Uint8Array(await inflate(raw, false));
      else if (comp === 5) bytes = new Uint8Array(lzwDecode(raw, tileBytes));
      else throw new Error("unsupported TIFF compression " + comp + " (1=none, 5=LZW, 8=deflate are supported)");
      if (pred === 2) bytes = new Uint8Array(undoPredictor(bytes, bytesPerTileRow, stride, bps[0] / 8));
      if (bytes.length !== tileBytes && b < offsets.length - 1) {
        add("decode_len", "Decoded block length matches geometry", false, bytes.length, tileBytes,
          "Block " + b + "; predictor/compression may be mis-parsed.");
        break;
      }
      var tx = tiled ? (b % nColsTiles) * tw : 0;
      var ty = tiled ? Math.floor(b / nColsTiles) * th : b * th;
      var rowsHere = Math.min(th, height - ty), colsHere = Math.min(tw, width - tx);
      for (var yy = 0; yy < rowsHere; yy++) {
        var src = (yy * tw) * 4, dst = ((ty + yy) * width + tx) * 4;
        decoded.set(bytes.subarray(src, src + colsHere * 4), dst);
      }
    }
    var f32 = new DataView(decoded.buffer);
    for (var p = 0; p < width * height; p++) {
      var v = f32.getFloat32(p * 4, little);
      stats.n++;
      if (Number.isNaN(v)) {
        stats.nan++;
        var nr = (p / width) | 0, nc = p % width;
        if (stats.nanRow0 === null) { stats.nanRow0 = nr; stats.nanRow1 = nr; stats.nanCol0 = nc; stats.nanCol1 = nc; }
        else {
          if (nr < stats.nanRow0) stats.nanRow0 = nr;
          if (nr > stats.nanRow1) stats.nanRow1 = nr;
          if (nc < stats.nanCol0) stats.nanCol0 = nc;
          if (nc > stats.nanCol1) stats.nanCol1 = nc;
        }
        continue;
      }
      if (!isFinite(v)) { stats.inf++; continue; }
      stats.finite++;
      if (v < stats.min) stats.min = v;
      if (v > stats.max) stats.max = v;
      if (v < 0) { stats.neg++; if (stats.outOfRange.length < 8) stats.outOfRange.push({ row: (p / width) | 0, col: p % width, value: v }); }
      else if (v > 1) { stats.gt1++; if (stats.outOfRange.length < 8) stats.outOfRange.push({ row: (p / width) | 0, col: p % width, value: v }); }
      else if (v === 0) stats.zero++;
      else { stats.nonzero++; if (v === 1) stats.one++; }
    }

    add("range", "Every value is in [0, 1]  <-- the rule that produced the organiser's rejection",
      stats.neg === 0 && stats.gt1 === 0,
      "min " + (stats.finite ? stats.min : "n/a") + ", max " + (stats.finite ? stats.max : "n/a") +
      ", " + stats.neg + " below 0, " + stats.gt1 + " above 1",
      "min >= " + REF.vMin + " and max <= " + REF.vMax,
      stats.outOfRange.length ? "First offenders: " + stats.outOfRange.map(function (o) {
        return "(" + o.row + "," + o.col + ")=" + o.value;
      }).join(" ") : "");
    add("inf", "No infinite values", stats.inf === 0, stats.inf + " Inf", "0 Inf",
      "Infinity is neither a probability nor the 'null or nan' the problem page allows outside the bounds.");
    add("nan", "NaN pixels and their bounding box (informational)", true,
      stats.nan + " NaN" + (stats.nan ? ", rows " + stats.nanRow0 + "-" + stats.nanRow1 +
        ", cols " + stats.nanCol0 + "-" + stats.nanCol1 : ""),
      "0, or confined to the area outside the study footprint",
      "The problem page explicitly permits null/nan OUTSIDE the bounds. The organiser's own " +
      "data/sample_submission.tif carries exactly 7,111,787 NaN pixels (measured), so NaN alone is not a " +
      "defect. This repository's candidates write 0.0 there and are all-finite - the stricter reading.", "info");
    add("nonzero", "Non-zero pixels (the emission budget)", stats.nonzero >= 0,
      stats.nonzero + " pixels > 0 (" + (100 * stats.nonzero / stats.n).toFixed(4) + "% of the grid)",
      "no format requirement",
      "Under the official distance-weighted Tversky metric (alpha=0.2, beta=0.8, R=300 m = 3 px) the " +
      "marginal rule at a board DTI of 0.2778 is to emit a pixel only if it lies within 2.24 px of a real " +
      "fault. Budget size is strategy, not format.", "info");
    var nodataStr = t[42113] && t[42113].values
      ? String.fromCharCode.apply(null, t[42113].values).replace(/\0+$/, "").trim() : null;
    var nodataOk = nodataStr === null || nodataStr.toLowerCase() === "nan" ||
      (!isNaN(parseFloat(nodataStr)) && parseFloat(nodataStr) >= 0 && parseFloat(nodataStr) <= 1);
    add("nodata", "NoData tag, if present, is absent, nan, or a finite value in [0, 1]", nodataOk,
      nodataStr === null ? "(absent)" : nodataStr, "absent, nan, or in [0,1]",
      "GDAL_NODATA tag 42113. A nodata tag of -3.4e38 (the float32 sentinel) is what the training raster carries " +
      "and is outside [0,1].");

    var hard = checks.filter(function (c) { return c.severity === "hard"; });
    var npass = hard.filter(function (c) { return c.pass; }).length;
    return {
      file: name, diskBytes: diskBytes, zip: zipInfo, compression: comp, predictor: pred,
      tiled: !!tiled, tileWidth: tw, tileHeight: th, littleEndian: little,
      geoKeys: gk, checks: checks, stats: stats,
      passed: npass, total: hard.length,
      ok: npass === hard.length,
      ms: ms,
      reference: REF,
      reference_class: "MEASURED from the organiser template data/sample_submission.tif, not assumed"
    };
  }

  var api = { checkFile: checkFile, checkTiff: checkTiff, unzipSingleTif: unzipSingleTif, REF: REF, lzwDecode: lzwDecode };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.GEMSTIF = api;
})();
