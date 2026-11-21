package com.wiiz.app;

import android.content.Intent;
import android.app.AlertDialog;
import java.io.OutputStream;
import java.io.FileInputStream;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.os.Build;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.content.res.ColorStateList;
import android.widget.Button;
import java.util.HashSet;
import java.util.Set;
import android.widget.RelativeLayout;
import android.widget.Toast;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import org.libsdl.app.SDLActivity;

/** Platform file selection only; ROM validation and emulation stay in the native app. */
public class WiizActivity extends SDLActivity {
    public int[] renderFilename(String text,int size,int width){
        android.graphics.Paint paint=new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        paint.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));paint.setTextSize(size);paint.setColor(0xfff0f0f0);
        android.graphics.Paint.FontMetrics metrics=paint.getFontMetrics();
        int height=(int)Math.ceil(metrics.descent-metrics.ascent)+8;
        android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(width,height,android.graphics.Bitmap.Config.ARGB_8888);
        android.graphics.Canvas canvas=new android.graphics.Canvas(image);canvas.drawColor(0xff000000);
        String visible=android.text.TextUtils.ellipsize(text,new android.text.TextPaint(paint),width,android.text.TextUtils.TruncateAt.END).toString();
        canvas.drawText(visible,0,4-metrics.ascent,paint);
        int[] pixels=new int[width*height];image.getPixels(pixels,0,width,0,0,width,height);image.recycle();return pixels;
    }
    private static final int PICK_ROM=9101, PICK_FOLDER=9104;
    private SharedFolder storage;
    private static native boolean hasActiveGame();
    private static native boolean openRomPath(byte[] utf8);
    public boolean storageReady(){return storage!=null&&storage.ready();}
    public boolean storageExists(String path)throws java.io.IOException{storageFlush();return storage.exists(path);}
    public void storageMkdir(String path)throws java.io.IOException{storageFlush();storage.mkdir(path);}
    public byte[] storageRead(String path,int limit)throws java.io.IOException{storageFlush();return storage.read(path,limit);}
    private SaveQueue saveQueue;
    public void storageWrite(String path,byte[] bytes)throws java.io.IOException{saveQueue.write(path,bytes);}
    public String storageFailure(){return saveQueue.failure();}
    public void storageFlush()throws java.io.IOException{saveQueue.flush();}
    private void chooseFolder(){
        if(hasActiveGame()){Toast.makeText(this,"保存先の変更はアプリを終了して開き直してから行ってください",Toast.LENGTH_LONG).show();return;}
        releaseButtons();Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        if(Build.VERSION.SDK_INT>=26)intent.putExtra(android.provider.DocumentsContract.EXTRA_INITIAL_URI,Uri.parse("content://com.android.externalstorage.documents/document/primary%3ADocuments"));
        startActivityForResult(intent,PICK_FOLDER);
    }
    private void chooseDocument(int request) {
        releaseButtons();
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        try { startActivityForResult(intent, request); }
        catch (android.content.ActivityNotFoundException ex) {
            Toast.makeText(this, "ファイル選択アプリがありません", Toast.LENGTH_LONG).show();
        }
    }
    private Button importButton;
    private RelativeLayout controls;
    private int layoutWidth, layoutHeight;
    private int safeLeft, safeTop, safeRight, safeBottom;

    private void layoutSafeArea() {
        if (controls == null) return;
        RelativeLayout.LayoutParams params = new RelativeLayout.LayoutParams(
                Math.max(1, mLayout.getWidth() - safeLeft - safeRight),
                Math.max(1, mLayout.getHeight() - safeTop - safeBottom));
        params.leftMargin = safeLeft;
        params.topMargin = safeTop;
        controls.setLayoutParams(params);
        arrange(params.width, params.height);
    }
    private final Set<Integer> heldButtons = new HashSet<>();
    private static native void touchKey(int action, boolean down);

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void styleButton(Button button, boolean round) {
        GradientDrawable background = new GradientDrawable();
        background.setShape(round ? GradientDrawable.OVAL : GradientDrawable.RECTANGLE);
        if (!round) background.setCornerRadius(dp(3));
        background.setColor(round ? 0xffa3333f : 0xff344154);
        // The platform Button background has top/bottom insets. On short
        // landscape buttons those leave only a thin strip behind the label.
        button.setBackgroundTintList(null);
        button.setBackground(new android.graphics.drawable.RippleDrawable(
                ColorStateList.valueOf(0x40ffffff), background, null));
        button.setStateListAnimator(null);
        button.setElevation(0);
        button.setGravity(android.view.Gravity.CENTER);
        button.setPadding(0, 0, 0, 0);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setTextColor(Color.WHITE);
        button.setTypeface(null, Typeface.BOLD);
        fitButtonLabel(button);
    }

    private void fitButtonLabel(Button button) {
        final float preferredSize = button.getTextSize();
        button.setSingleLine(true);
        button.setIncludeFontPadding(false);
        button.setMinHeight(0);
        button.setMinimumHeight(0);
        // Measure with Android's actual font, including the user's font scale.
        // Landscape utility buttons can be much shorter than their portrait size.
        button.addOnLayoutChangeListener((view, l, t, r, b, ol, ot, or, ob) -> {
            int width = r - l - button.getCompoundPaddingLeft() - button.getCompoundPaddingRight() - dp(4);
            int height = b - t - button.getCompoundPaddingTop() - button.getCompoundPaddingBottom() - dp(2);
            if (width <= 0 || height <= 0) return;
            android.text.TextPaint paint = new android.text.TextPaint(button.getPaint());
            paint.setTextSize(preferredSize);
            CharSequence text = button.getText();
            if (button.getTransformationMethod() != null)
                text = button.getTransformationMethod().getTransformation(text, button);
            android.graphics.Paint.FontMetrics metrics = paint.getFontMetrics();
            float scale = Math.min(1f, Math.min(width / Math.max(1f, paint.measureText(text.toString())),
                    height / Math.max(1f, metrics.bottom - metrics.top)));
            float size = preferredSize * scale;
            if (Math.abs(button.getTextSize() - size) > 0.1f)
                button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_PX, size);
        });
    }

    private Button keyButton(String label, int action) {
        Button button = new Button(this);
        button.setText(label);
        if(action==6)button.setContentDescription("Select");
        if(action==7)button.setContentDescription("Start");
        button.setTextSize(action <= 3 ? 36 : action <= 5 ? 30 : action <= 7 ? 20 : 14);
        styleButton(button, action >= 4 && action <= 7);
        button.setOnTouchListener((view, event) -> {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    heldButtons.add(action);
                    touchKey(action, true);
                    view.setPressed(true);
                    return true;
                case MotionEvent.ACTION_MOVE:
                    if (event.getX() < 0 || event.getY() < 0 || event.getX() >= view.getWidth() || event.getY() >= view.getHeight()) {
                        if (heldButtons.remove(action)) touchKey(action, false);
                        view.setPressed(false);
                    }
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (heldButtons.remove(action)) touchKey(action, false);
                    view.setPressed(false);
                    return true;
                default: return true;
            }
        });
        return button;
    }

    private void releaseButtons() {
        for (int action : heldButtons) touchKey(action, false);
        heldButtons.clear();
    }

    @Override protected void onPause() {
        releaseButtons();
        super.onPause();
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        if (!focused) releaseButtons();
        super.onWindowFocusChanged(focused);
    }

    private void place(View view, int x, int y, int width, int height) {
        RelativeLayout.LayoutParams params = new RelativeLayout.LayoutParams(width, height);
        params.leftMargin = x; params.topMargin = y;
        controls.addView(view, params);
    }

    private void arrange(int width, int height) {
        if (width <= 0 || height <= 0 || (width == layoutWidth && height == layoutHeight)) return;
        layoutWidth = width; layoutHeight = height;
        releaseButtons();
        if (importButton.getParent() != null) ((android.view.ViewGroup)importButton.getParent()).removeView(importButton);
        controls.removeAllViews();
        ControllerLayout layout=new ControllerLayout(width,height,getResources().getDisplayMetrics().density);
        int[] box=layout.screen;
        RelativeLayout.LayoutParams surface=new RelativeLayout.LayoutParams(box[2],box[3]);
        surface.leftMargin=safeLeft+box[0];surface.topMargin=safeTop+box[1];
        mSurface.setLayoutParams(surface);
        String[] labels={"↑","↓","←","→","A","B","SEL","STA","設定","SAVE 1","LOAD 1","マップ","リセット","再読込","アイテム"};
        for(java.util.Map.Entry<Integer,int[]> entry:layout.buttons.entrySet()){
            int action=entry.getKey();int[] b=entry.getValue();
            View view=action==-1?importButton:keyButton(labels[action],action);
            place(view,b[0],b[1],b[2],b[3]);
        }

    }
    @Override protected String[] getLibraries() { return new String[] { "SDL3", "main" }; }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        storage=new SharedFolder(this);
        saveQueue=new SaveQueue((path,bytes)->storage.write(path,bytes),
            message->runOnUiThread(()->Toast.makeText(this,message,Toast.LENGTH_LONG).show()));
        if (mLayout == null) return;
        mLayout.setBackgroundColor(0xff101722);
        controls = new RelativeLayout(this);
        controls.setMotionEventSplittingEnabled(true);
        mLayout.addView(controls, new RelativeLayout.LayoutParams(-1, -1));
        importButton = new Button(this);
        importButton.setText("ファイル");
        importButton.setTextSize(14);
        styleButton(importButton, false);
        importButton.setContentDescription("ROMを取り込む");
        // Reserve system bars even when SDL temporarily hides them. This keeps
        // the controls clear when Android restores gesture/three-button navigation.
        mLayout.setOnApplyWindowInsetsListener((view, insets) -> {
            int left, top, right, bottom;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsetsIgnoringVisibility(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                android.graphics.Insets gestures = insets.getInsets(WindowInsets.Type.mandatorySystemGestures());
                left = Math.max(bars.left, gestures.left);
                top = Math.max(bars.top, gestures.top);
                right = Math.max(bars.right, gestures.right);
                bottom = Math.max(bars.bottom, gestures.bottom);
            } else {
                left = insets.getStableInsetLeft(); top = insets.getStableInsetTop();
                right = insets.getStableInsetRight(); bottom = insets.getStableInsetBottom();
            }
            // A little breathing room above navigation, in addition to its actual height.
            bottom += dp(8);
            if (left != safeLeft || top != safeTop || right != safeRight || bottom != safeBottom) {
                safeLeft = left; safeTop = top; safeRight = right; safeBottom = bottom;
                layoutWidth = layoutHeight = 0;
                layoutSafeArea();
            }
            return insets;
        });
        mLayout.addOnLayoutChangeListener((v, l, top, r, bottom, ol, ot, oright, ob) -> layoutSafeArea());
        mLayout.post(() -> { mLayout.requestApplyInsets(); layoutSafeArea(); });
        importButton.setOnClickListener(v -> {
            releaseButtons();new AlertDialog.Builder(this).setTitle("Wiizフォルダー / ROM")
                .setItems(new String[]{"ROMを取り込む","保存フォルダーを指定"},(d,which)->{
                    if(which==0&&storageReady())chooseDocument(PICK_ROM);else chooseFolder();
                }).show();
        });
        if(!storageReady())mLayout.post(()->new AlertDialog.Builder(this)
            .setMessage("Documentsを選ぶと、その中にWiiz/Rom・Save・stateを作成します。既存のWiizを直接選んでも構いません。SAVとステートはこの場所だけに保存します。")
            .setPositiveButton("フォルダーを選ぶ",(d,w)->chooseFolder()).setCancelable(false).show());
        else new Thread(()->{try{storage.cacheRoms(new File(getFilesDir(),"shared-rom-cache"));touchKey(13,true);touchKey(13,false);}catch(Exception ex){runOnUiThread(()->Toast.makeText(this,ex.getMessage(),Toast.LENGTH_LONG).show());}},"Wiiz-ROM-cache").start();
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if(request==PICK_FOLDER){
            if(result!=RESULT_OK||data==null||data.getData()==null)return;
            final Intent selection=data;
            new Thread(()->{try{
                storage.select(selection.getData(),selection.getFlags());
                storage.cacheRoms(new File(getFilesDir(),"shared-rom-cache"));touchKey(13,true);touchKey(13,false);
                runOnUiThread(()->Toast.makeText(this,"Wiiz/Rom・Save・stateを使用します。ROMを取り込んで開始してください。",Toast.LENGTH_LONG).show());
            }catch(Exception ex){runOnUiThread(()->Toast.makeText(this,"設定失敗: "+ex.getMessage(),Toast.LENGTH_LONG).show());}},"Wiiz-folder").start();return;
        }
        if(request!=PICK_ROM||result!=RESULT_OK||data==null||data.getData()==null)return;
        final Uri uri = data.getData();
        importButton.setEnabled(false);
        new Thread(() -> {
            File temporary = null;
            try {
                String name = "imported.nes";
                try (Cursor cursor = getContentResolver().query(uri,
                        new String[] { OpenableColumns.DISPLAY_NAME }, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0)) name = cursor.getString(0);
                }
                if (!name.toLowerCase(java.util.Locale.ROOT).endsWith(".nes"))
                    throw new java.io.IOException(".nesファイルを選んでください");
                StringBuilder safeName=new StringBuilder();
                for(char ch:name.toCharArray())safeName.append(ch<' '||ch=='/'||ch=='\\'? '_' : ch);
                name=safeName.toString();
                if(name.codePointCount(0,name.length())>100)name=name.substring(0,name.offsetByCodePoints(0,96))+".nes";
                File staging = new File(getCacheDir(), "rom-import");
                if (!staging.isDirectory() && !staging.mkdirs()) throw new java.io.IOException("保存先を作成できません");
                temporary = new File(staging, name);
                try (InputStream input = getContentResolver().openInputStream(uri);
                     FileOutputStream output = new FileOutputStream(temporary)) {
                    if (input == null) throw new java.io.IOException("ファイルを開けません");
                    byte[] buffer = new byte[8192]; int count; long total = 0;
                    while ((count = input.read(buffer)) != -1) {
                        total += count;
                        if (total > 4 * 1024 * 1024) throw new java.io.IOException("ROMが大きすぎます（上限4MiB）");
                        output.write(buffer, 0, count);
                    }
                    output.getFD().sync();
                }
                byte[] rom;
                try(InputStream in=new FileInputStream(temporary);java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()){
                    byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);rom=out.toByteArray();
                }
                if(storage.exists("Rom/"+name)){
                    if(!java.util.Arrays.equals(rom,storage.read("Rom/"+name,4*1024*1024)))throw new java.io.IOException("同名の異なるROMが存在します。名前を変更してください");
                }else storage.write("Rom/"+name,rom);
                // SDL's existing drop-file JNI API queues delivery on the native event loop.
                File cache=new File(getFilesDir(),"shared-rom-cache");
                if(!cache.isDirectory()&&!cache.mkdirs())throw new java.io.IOException("ROMキャッシュ作成不可");
                File cached=new File(cache,name);
                try(FileOutputStream out=new FileOutputStream(cached)){out.write(rom);}
                temporary.delete();
                if(!openRomPath(cached.getAbsolutePath().getBytes(java.nio.charset.StandardCharsets.UTF_8)))throw new java.io.IOException("ROM起動要求を送信できません");
            } catch (Exception ex) {
                if (temporary != null) temporary.delete();
                final String message = ex.getMessage();
                runOnUiThread(() -> Toast.makeText(this, "取り込み失敗: " + message, Toast.LENGTH_LONG).show());
            } finally {
                runOnUiThread(() -> { if (!isDestroyed()) importButton.setEnabled(true); });
            }
        }, "Wiiz-ROM-import").start();
    }
}
