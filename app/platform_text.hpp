#pragma once
#include <SDL3/SDL.h>
#include <map>
#include <string>
#include <vector>
#include <stdexcept>
#ifdef __ANDROID__
#include <jni.h>
#include <codecvt>
#include <locale>
#elif defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
// OS font rasterization for filenames; no replacement/transliteration of Unicode names.
class FileLabelRenderer {
    SDL_Renderer* renderer_;
    std::map<std::string,SDL_Texture*> cache_;
public:
    explicit FileLabelRenderer(SDL_Renderer* r):renderer_(r){}
    ~FileLabelRenderer(){clear();}
    void clear(){for(auto& item:cache_)SDL_DestroyTexture(item.second);cache_.clear();}
    void draw(float x,float y,const std::string& value,int size=40,int width=840){
        const auto key=std::to_string(size)+":"+std::to_string(width)+":"+value;
        auto found=cache_.find(key);
        if(found==cache_.end()){
            int height=size+20;
            std::vector<uint32_t> pixels;
#ifdef __ANDROID__
            auto* env=static_cast<JNIEnv*>(SDL_GetAndroidJNIEnv());
            auto activity=static_cast<jobject>(SDL_GetAndroidActivity());
            auto type=env->GetObjectClass(activity);
            std::wstring_convert<std::codecvt_utf8_utf16<char16_t>,char16_t> converter;
            auto utf16=converter.from_bytes(value);
            auto text=env->NewString(reinterpret_cast<const jchar*>(utf16.data()),int(utf16.size()));
            auto method=env->GetMethodID(type,"renderFilename","(Ljava/lang/String;II)[I");
            auto image=static_cast<jintArray>(env->CallObjectMethod(activity,method,text,size,width));
            env->DeleteLocalRef(text);env->DeleteLocalRef(type);env->DeleteLocalRef(activity);
            if(env->ExceptionCheck()){env->ExceptionClear();throw std::runtime_error("Filename font rendering failed");}
            if(!image)throw std::runtime_error("Filename font unavailable");
            const auto length=env->GetArrayLength(image);
            height=length/width;pixels.resize(length);
            env->GetIntArrayRegion(image,0,length,reinterpret_cast<jint*>(pixels.data()));env->DeleteLocalRef(image);
#elif defined(_WIN32)
            int count=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,value.data(),int(value.size()),nullptr,0);
            if(!count&&!value.empty())throw std::runtime_error("Invalid UTF-8 filename");
            std::wstring text(count,0);MultiByteToWideChar(CP_UTF8,0,value.data(),int(value.size()),text.data(),count);
            HDC dc=CreateCompatibleDC(nullptr);
            BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;info.bmiHeader.biCompression=BI_RGB;
            void* bits=nullptr;HBITMAP bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&bits,nullptr,0);
            HFONT font=CreateFontW(-size,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,ANTIALIASED_QUALITY,DEFAULT_PITCH,L"Yu Gothic UI");
            if(!dc||!bitmap||!font){if(font)DeleteObject(font);if(bitmap)DeleteObject(bitmap);if(dc)DeleteDC(dc);throw std::runtime_error("OS filename font unavailable");}
            auto oldBitmap=SelectObject(dc,bitmap);auto oldFont=SelectObject(dc,font);
            RECT rect{0,0,width,height};FillRect(dc,&rect,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));SetTextColor(dc,RGB(240,240,240));SetBkMode(dc,TRANSPARENT);
            DrawTextW(dc,text.data(),int(text.size()),&rect,DT_LEFT|DT_TOP|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
            GdiFlush();auto* source=static_cast<uint32_t*>(bits);pixels.assign(source,source+width*height);for(auto& p:pixels)p|=0xff000000;
            SelectObject(dc,oldFont);SelectObject(dc,oldBitmap);DeleteObject(font);DeleteObject(bitmap);DeleteDC(dc);
#else
            SDL_SetRenderScale(renderer_,3,3);SDL_RenderDebugText(renderer_,x/3,y/3,value.c_str());SDL_SetRenderScale(renderer_,1,1);return;
#endif
            if(cache_.size()>=64)clear();
            auto* texture=SDL_CreateTexture(renderer_,SDL_PIXELFORMAT_ARGB8888,SDL_TEXTUREACCESS_STATIC,width,height);
            if(!texture)throw std::runtime_error(SDL_GetError());
            if(!SDL_UpdateTexture(texture,nullptr,pixels.data(),width*4)){SDL_DestroyTexture(texture);throw std::runtime_error(SDL_GetError());}
            found=cache_.emplace(key,texture).first;
        }
        float w,h;SDL_GetTextureSize(found->second,&w,&h);SDL_FRect box{x,y,w,h};SDL_RenderTexture(renderer_,found->second,nullptr,&box);
    }
};
