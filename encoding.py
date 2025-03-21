import os
import cv2 as cv
import numpy as np
from progress.bar import Bar
import binascii

class Buffer:
    def __init__(self, buffer):
        self.buffer = buffer
        self.cursor = 0

    def get_data(self, data_len):
        ret = int(self.buffer[self.cursor:self.cursor+data_len], base=16)
        self.cursor = self.cursor + data_len
        return ret
    
    def end(self):
        return len(self.buffer[self.cursor:]) == 0

class Frame:
    def __init__(self, frame_height, frame_width):
        self.frame = np.ndarray((frame_height,frame_width,3), dtype=np.uint8)
        self.frame_height = frame_height
        self.frame_width = frame_width
        self.cursor = 0
    
    def insert_pixel(self, pixel):
        self.frame[self.cursor//self.frame_width][self.cursor%self.frame_width] = pixel
        self.cursor += 1
    
    def end(self):
        return self.cursor == self.frame_height * self.frame_width
    
    def get_frame(self):
        return self.frame

class Encoding:
    encodings = {
        "gtvf"
    }

    def __init__(self, encoding=''):
        self.encoding = encoding

    def encode(self, inpath, outpath):
        file_name, _ = os.path.splitext(os.path.basename(inpath))
        outfile = os.path.join(outpath, "{}.{}".format(file_name, self.encoding))

        match self.encoding:
            case "gtvf":
                self.gtvf_encoder(inpath, outfile)
            case _:
                pass

    def decode(self, inpath, outpath):
        file_name, _ = os.path.splitext(os.path.basename(inpath))
        outfile = os.path.join(outpath, "{}.avi".format(file_name))

        match self.encoding:
            case "gtvf":
                self.gtvf_decoder(inpath, outfile)
            case _:
                pass

    def gtvf_encoder(self, infile, outfile):
        with open(outfile, mode='wb') as file:
            cap = cv.VideoCapture(infile)

            height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
            width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))

            file.write(binascii.unhexlify("{:04X}".format(height)))
            file.write(binascii.unhexlify("{:04X}".format(width)))

            totalframes = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
            bar = Bar('Encoding Video', max=totalframes, suffix='%(percent)d%%')

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    print("Can't receive frame (stream end?). Exiting ...")
                    break

                RGBframe = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

                # La donnée sera de 16 bits pour la répétition et 8 bits pour la nuance de gris.
                # De 0x0000 à 0x7FFF, les non-répétitions et de 0x8000 à 0xFFFF, les répétitions.
                rle_offset = int("8000", base=16)
                dif_max = int("7FFF", base=16)
                rep_max = int("FFFF", base=16)

                last_sequence = []
                last_pixel = ''
                pixel_count = -1

                # Machine à état :
                # 0: choisir le mode (répétitions ou différences)
                # 1: mode répétitions
                # 2: mode différences
                etat = 0

                for rowIndex, row in enumerate(RGBframe):
                    for pixelIndex, pixel in enumerate(row):
                        current_pixel = "{:02X}".format(pixel[0])
                        pixel_count += 1

                        if last_pixel == '':
                            last_pixel = current_pixel
                            continue

                        match etat:
                            case 0: # choisir le mode
                                if last_pixel == current_pixel:
                                    etat = 1
                                else:
                                    etat = 2
                            case _:
                                pass

                        match etat:
                            case 1: # mode répétitions
                                if last_pixel != current_pixel or pixel_count == rep_max - rle_offset or (rowIndex == height-1 and pixelIndex == width-1):
                                    if rowIndex == height-1 and pixelIndex == width-1:
                                        pixel_count += 1

                                    file.write(binascii.unhexlify("{:04X}{}".format(rle_offset + pixel_count, last_pixel)))

                                    pixel_count = 0
                                    etat = 0
                                    
                            case 2: # mode différences
                                last_sequence.append(last_pixel)
                                if last_pixel == current_pixel or pixel_count == dif_max or (rowIndex == height-1 and pixelIndex == width-1):
                                    if rowIndex == height-1 and pixelIndex == width-1:
                                        last_sequence.append(current_pixel)
                                        pixel_count += 1

                                    file.write(binascii.unhexlify("{:04X}".format(pixel_count)))
                                    for dif_pixel in last_sequence:
                                        file.write(binascii.unhexlify("{}".format(dif_pixel)))

                                    pixel_count = 0
                                    etat = 0
                                    last_sequence = []
                            case _:
                                pass

                        last_pixel = current_pixel

                cv.imshow('frame', frame)

                if cv.waitKey(1) == ord('q'):
                    break
                bar.next()
            bar.finish()
            cap.release()
            cv.destroyAllWindows()

    def gtvf_decoder(self, infile, outfile):
        with open(infile, mode='rb') as file:
            fourcc = cv.VideoWriter_fourcc(*'XVID')
            print('reading file...')
            
            buffer = Buffer(binascii.hexlify(file.read()).upper())

            frames_height = buffer.get_data(4)
            frames_width = buffer.get_data(4)

            out = cv.VideoWriter(outfile, fourcc, 30.0, (frames_width, frames_height))

            print('decoding video...')
            
            # La donnée sera de 16 bits pour la répétition et 24 bits pour la couleur.
            # De 0x0000 à 0x8000, les non-répétitions et de 0x8000 à 0xFFFF, les répétitions.
            rle_offset = int("8000", base=16)
            
            # Machine à état :
            # 0: lire les nombres
            # 1: lire les différences
            # 2: lire les répétitions
            etat = 0
            
            occurences = 0
            
            pixel = int("00",base=16)

            while not buffer.end():
                frame = Frame(frames_height,frames_width)

                while not frame.end():
                    match etat:
                        case 0: # lire les nombres
                            occurences = buffer.get_data(4)
                            if occurences < rle_offset:
                                etat = 1
                            else:
                                occurences -= rle_offset
                                pixel = buffer.get_data(2)
                                etat = 2
                        case 1: # lire les différences
                            pixel = buffer.get_data(2)
                            frame.insert_pixel([pixel,pixel,pixel])

                            occurences -= 1
                            if occurences == 0:
                                etat = 0
                        case 2: # lire les répétitions
                            frame.insert_pixel([pixel,pixel,pixel])

                            occurences -= 1
                            if occurences == 0:
                                etat = 0
                        case _:
                            pass
                
                new_frame = cv.cvtColor(frame.get_frame(), cv.COLOR_RGB2BGR)
                out.write(new_frame)
                # cv.imshow('frame', new_frame)
            
            out.release()
            cv.destroyAllWindows()
