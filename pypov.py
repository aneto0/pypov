import argparse
import math
import pygame
from pygame.locals import *

RED =  (255, 0, 0)
BLUE =  (0, 0, 255)
GRAY = (150, 150, 150)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

pygame.init()

def getAngleRads(angleDegs):
    return angleDegs * math.pi / 180

class ImageToLed:
    '''Interpolates an image color space to the led color space, i.e. how is the image seen by a set of rotating leds.
    '''

    def __init__(self, angleAverageSpan, angleAveragePoints, rAverageSpan, rAveragePoints):
        '''
        Args:
            angleAverageSpan: w.r.t. to the led angular position, what span (in degrees) is to be used to compute the average color
            angleAveragePoints: how many points between the current led angular position and the angleAverageSpan are to be considered
            rAverageSpan: w.r.t. to the led radial position, what span (in pixels) is to be used to compute the average color
            rAveragePoints: how many points between the current led radial position and the rAverageSpan are to be considered
        '''
        #The number of points must be even to include the led angle position itself
        if ((angleAveragePoints % 2) == 0):
            angleAveragePoints += 1
        if (angleAveragePoints > 1):
            #Note that the angleAverageSpan goes from angle-angleAverageSpan to angle+angleAverageSpan
            self.angleAverageResolution = angleAverageSpan / (angleAveragePoints - 1)
        else:
            self.angleAverageResolution = 0
        self.angleAverageResolution = getAngleRads(self.angleAverageResolution)
        
        #The number of points must be even to include the led r position itself
        if ((rAveragePoints % 2) == 0):
            rAveragePoints += 1
        if (rAveragePoints > 1):
            #Note that the rAverageResolution goes from ledRPosition-rAverageSpan to ledRPosition+rAverageSpan
            self.rAverageResolution = rAverageSpan / (rAveragePoints - 1)
        else:
            self.rAverageResolution = 0

        self.angleAveragePoints = angleAveragePoints
        self.rAveragePoints = rAveragePoints
        self.numberOfAveragedPixels = (angleAveragePoints * rAveragePoints)
        self.img = None

    def setImage(self, img):
        self.img = img
        self.imgBound = img.get_rect()

    def getLedColorArea(self, angle, ledRPosition):
        ''' Gets the points coordinates defining the area over which to average the led color
        Let the current led position be defined by p(ledRPosition, angle), where R is the distance to the center of the backgroundFrame and angle is the angle with the horizontal axis at the middle of the image
        For every angle between 0 and 2*pi, compute the average color in the polar region defined by the points p(ledRPosition - rAverageResolution * rAveragePoints / 2, angle - angleAverageResolution * angleAveragePoints / 2) and p (ledRPosition + rAverageResolution * rAveragePoints / 2, angle + angleAverageResolution * angleAveragePoints / 2)
        
        Returns:
            A matrix where each line contains the (x, y) pairs of a complete angular scan for a given r value (i.e. each line corresponds to a different r value).
        '''
        rr = []
        for t in range(self.angleAveragePoints):
            dangle = getAngleRads(angle)
            #Note that the angleAverageResolution is already in rads (see __init__)
            dangle += self.angleAverageResolution * (t - (self.angleAveragePoints - 1) / 2) 
            rri = []
            for r in range(self.rAveragePoints):
                dr = ledRPosition
                dr += self.rAverageResolution * (r - (self.rAveragePoints - 1) / 2)
                xPosition = self.imgBound.centerx
                xPosition += dr * math.cos(dangle)
                yPosition = self.imgBound.centery
                yPosition += dr * math.sin(dangle)
                yPosition = self.imgBound.height - yPosition
                rri.append((xPosition, yPosition))
            rr.append(rri)

        return rr

    def getLedColor(self, angle, ledRPosition):

        redValue = 0
        greenValue = 0
        blueValue = 0
        alphaValue = 0
        lastGoodPixel = (backgroundFrameColor[0], backgroundFrameColor[1], backgroundFrameColor[2], 255)
        averageArea = self.getLedColorArea(angle, ledRPosition)
        for rr in averageArea:
            for aa in rr:
                xPosition = aa[0]
                yPosition = aa[1]
                if ((xPosition > -1) and (xPosition < self.imgBound.width) and (yPosition > -1) and (yPosition < self.imgBound.height)):
                    imgPixelColor = img.get_at((int(xPosition), int(yPosition)))
                    lastGoodPixel = imgPixelColor
                else:
                    imgPixelColor = lastGoodPixel 

                #Do not divide by pixels that are transparent
                alphaValue = imgPixelColor[3]
                if (alphaValue < 1):
                    imgPixelColor[0] = backgroundFrameColor[0]
                    imgPixelColor[1] = backgroundFrameColor[1]
                    imgPixelColor[2] = backgroundFrameColor[2]
                redValue += (imgPixelColor[0] * alphaValue / 255)
                greenValue += (imgPixelColor[1] * alphaValue / 255)
                blueValue += (imgPixelColor[2] * alphaValue / 255)

        redValue /= self.numberOfAveragedPixels 
        greenValue /= self.numberOfAveragedPixels
        blueValue /= self.numberOfAveragedPixels
        averageColor = (redValue, greenValue, blueValue)

        return averageColor

    def getLedColors(self, angleIncrement, ledRPosition):
        ret = []
        angle = 0
        while (angle < 360):
            ret.append(self.getLedColor(angle, ledRPosition))
            angle += angleIncrement
        return ret

class LedDraw:
    ''' Plots the leds on the screen. The leds are rotated with the defined angleIncrement.
    '''

    def __init__(self, surf, angleIncrement, distanceBetweenLeds, numberOfLeds, ledRadius, ledCenterOffset, shaftRadius = 3, shaftColor = BLACK):
        '''
        Args:
            surf: target surface where to draw
            angleIncrement: angular resolution in degrees 
            distanceBetweenLeds: radial distance between the leds in pixels
            numberOfLeds: total number of LEDs
            ledRadius: LED radius in pixels
            ledCenterOffset: radial distance between the first led and the shaft in pixels
            shaftRadius: radius of the shaft in pixels
            shaftColor: color of the shaft
        '''
        self.surf = surf
        self.angleIncrement = angleIncrement
        self.distanceBetweenLeds = distanceBetweenLeds
        self.numberOfLeds = numberOfLeds
        self.ledRadius = ledRadius
        self.ledCenterOffset = ledCenterOffset
        self.shaftRadius = shaftRadius
        self.shaftColor = shaftColor

    def setColorMap(self, ledColors):
        '''Sets the color of all leds for every possible angular and radial position (the radial position is obviously fixed for each led index).
        '''
        self.ledColors = ledColors

    def drawLed(self, ledIdx, angle, border):
        surfRect = self.surf.get_rect()
        angleIdx = int(angle / self.angleIncrement)
        angleRads = angle * math.pi / 180
        ledXPosition = surfRect.centerx
        ledXPosition += (self.ledCenterOffset + ledIdx * self.distanceBetweenLeds) * math.cos(angleRads)
        ledXPosition = int(ledXPosition)
        ledYPosition = surfRect.centery
        ledYPosition += (self.ledCenterOffset + ledIdx * self.distanceBetweenLeds) * math.sin(angleRads)
        ledYPosition = int(surfRect.height - ledYPosition)
        pygame.draw.circle(self.surf, self.ledColors[ledIdx][angleIdx], (ledXPosition, ledYPosition), self.ledRadius * 1.10, 0)
        #Difuse the color
        pygame.draw.circle(self.surf, self.ledColors[ledIdx][angleIdx], (ledXPosition, ledYPosition), self.ledRadius, 0)
        if (border):
            pygame.draw.circle(self.surf, ledLineColor, (ledXPosition, ledYPosition), self.ledRadius, 1)

    def draw(self, angle, border):
        #Draw the center shaft point
        pygame.draw.circle(self.surf, self.shaftColor, self.surf.get_rect().center, self.shaftRadius)
        #Draw the leds
        for ledIdx in range(self.numberOfLeds):
            self.drawLed(ledIdx, angle, border)

    def drawAveragedAreas(self, angle, averagedPolyCoords):
        for ledIdx in range(len(averagedPolyCoords)):
            angleIdx = int(angle / self.angleIncrement)
            averageColor = self.ledColors[ledIdx][angleIdx]
            averagedPolyCoordsI = averagedPolyCoords[ledIdx]
            #Two of the segments are in reality arcs (i.e. the colour is computed using arcs!). Too lazy to bother drawing them as arcs.
            pygame.draw.polygon(self.surf, averageColor, averagedPolyCoordsI)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = 'Get metadata from IDM')
    #Get the image to display
    parser.add_argument('-i', '--image', type=str, help='Image to which the POV is to be applied', default='images/bird.png')
    parser.add_argument('-a', '--alpha', type=int, help='Alpha of the background image [0, 255]', default=10)
    parser.add_argument('-w', '--backgroundFrameWidth', type=int, help='Width of the background frame', default=600)
    parser.add_argument('-n', '--numberleds', type=int, help='Number of LEDs', default=15)
    parser.add_argument('-u', '--units', type=str, help='Units to be used when interpreting the specified configurable distances (mm or pixels)', default='pixels')
    parser.add_argument('-lr', '--ledradius', type=int, help='LED radius', default=8)
    parser.add_argument('-ls', '--ledseparation', type=int, help='Distance between the borders of two leds', default=1)
    parser.add_argument('-as', '--angleavgspan', type=int, help='Angular span to be used when computing the average color (degrees)', default=1)
    parser.add_argument('-ap', '--angleavgpoints', type=int, help='Resolution in points of the angular average span', default=3)
    parser.add_argument('-rs', '--radialavgspan', type=int, help='Radial span to be used when computing the average color (distance)', default=10)
    parser.add_argument('-rp', '--radialavgpoints', type=int, help='Resolution in points of the radial average span', default=3)
    parser.add_argument('-lco', '--ledcenteroffset', type=int, help='Offset of the first led with respect to the center', default=15)
    

    args = parser.parse_args()

    #Set the screen properties
    screenSize = (int(args.backgroundFrameWidth), int(args.backgroundFrameWidth))
    screen = pygame.display.set_mode(screenSize)

    #All sizes in pixels
    #Size of the frame holding the pov
    backgroundFrame = Rect(0, 0, args.backgroundFrameWidth, args.backgroundFrameWidth)
    backgroundFrame.centerx = screen.get_rect().centerx
    backgroundFrame.centery = screen.get_rect().centery
    backgroundFrameColor = WHITE

    #Load the image
    img = pygame.image.load(args.image)
    img.convert()
    img.set_alpha(args.alpha)
    #Transform the image to the target resolution
    img = pygame.transform.scale(img, (args.backgroundFrameWidth, args.backgroundFrameWidth))
    imgRect = img.get_rect()
    imgRect.centerx = backgroundFrame.centerx
    imgRect.centery = backgroundFrame.centery

    #LEDS
    ledLineColor = BLACK

    #Image to led class
    imgToLed = ImageToLed(args.angleavgspan, args.angleavgpoints, args.radialavgspan, args.radialavgpoints)
    imgToLed.setImage(img)

    distanceBetweenLeds = 2 * args.ledradius + args.ledseparation
    angleIncrement = 1
    ledColors = []
    for ledIdx in range(args.numberleds):
        ledRPosition = (args.ledcenteroffset + ledIdx * distanceBetweenLeds)
        ledColorsI = imgToLed.getLedColors(angleIncrement, ledRPosition)
        ledColors.append(ledColorsI)

    ledDraw = LedDraw(screen, angleIncrement, distanceBetweenLeds, args.numberleds, args.ledradius, args.ledcenteroffset)
    ledDraw.setColorMap(ledColors)

    angle = 0
    raster = False
    running = True
    drawAverageArea = True
    
    imgBorderColor = (255, 0, 0, args.alpha)
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            if event.type == KEYDOWN:
                if event.key == K_RIGHT:
                    angle -= angleIncrement
                elif event.key == K_LEFT:
                    angle += angleIncrement
                elif event.key == K_UP:
                    raster = not raster

        if (angle == 360):
            angle = 0
        if (angle == -1):
            angle = 359
        #angle -= 1
        screen.fill(GRAY)

        pygame.draw.rect(screen, backgroundFrameColor, backgroundFrame)
        screen.blit(img, imgRect)
        pygame.draw.rect(screen, imgBorderColor, imgRect, 1)
        if (raster):
            #This is quite horrible. A better way of doing this is get the color of each led and diffuse on the surrounding pixels, summing the contribution of all the neighbours.
            #Once the RGB of each pixel has been computed, it is a matter of calling set_at
            for a in range(360):
                ledDraw.draw(a, False)
        else:
            ledDraw.draw(angle, True)
            if (drawAverageArea):
                averagedPolyCoords = []
                for ledIdx in range(args.numberleds):
                    ledRPosition = (args.ledcenteroffset + ledIdx * distanceBetweenLeds)
                    ledAveragedPolyCoords = imgToLed.getLedColorArea(angle, ledRPosition)
                    ri = ledAveragedPolyCoords[0]
                    xy0i = ri[0]
                    xy1i = ri[-1]
                    rf = ledAveragedPolyCoords[-1]
                    xy0f = rf[0]
                    xy1f = rf[-1]

                    averagedPolyCoords.append([xy0i, xy1i, xy1f, xy0f, xy0i])

                ledDraw.drawAveragedAreas(angle, averagedPolyCoords)
        pygame.display.flip()

    pygame.quit()


