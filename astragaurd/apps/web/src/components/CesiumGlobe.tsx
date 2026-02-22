import { useEffect, useRef } from 'react'
import * as Cesium from 'cesium'
import type { CesiumSnapshot, ConjunctionEvent } from '../types'

interface Props {
  snapshot: CesiumSnapshot | null
  timeIndex: number
  selectedEvent: ConjunctionEvent | null
  onTimeChange: (index: number) => void
  showContinents: boolean
}

export default function CesiumGlobe({ snapshot, timeIndex, selectedEvent, onTimeChange, showContinents }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const initializedRef = useRef(false)
  const pointPrimsRef = useRef<Cesium.PointPrimitive[]>([])
  const pointCollectionRef = useRef<Cesium.PointPrimitiveCollection | null>(null)
  const noradIndexMapRef = useRef<Map<number, number>>(new Map())
  const pulseEntityRef = useRef<Cesium.Entity | null>(null)
  const continentsRef = useRef<Cesium.GeoJsonDataSource | null>(null)
  const continentsLoadedRef = useRef(false)

  // Initialize viewer once
  useEffect(() => {
    if (initializedRef.current || !containerRef.current) return
    initializedRef.current = true

    try {
      // Suppress Ion token warning — we're not using Ion assets
      Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.stub'

      const viewer = new Cesium.Viewer(containerRef.current, {
        // v1.99+ API: baseLayer:false skips default imagery
        baseLayer: false as unknown as Cesium.ImageryLayer,
        terrainProvider: new Cesium.EllipsoidTerrainProvider(),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        skyBox: false as unknown as Cesium.SkyBox,
        skyAtmosphere: false as unknown as Cesium.SkyAtmosphere,
        requestRenderMode: false,
      })

      // Remove any imagery layers that snuck in
      viewer.scene.imageryLayers.removeAll()

      // Dark ocean blue globe
      viewer.scene.globe.baseColor = new Cesium.Color(0.03, 0.08, 0.18, 1.0)
      viewer.scene.globe.showGroundAtmosphere = false
      viewer.scene.globe.depthTestAgainstTerrain = false
      viewer.scene.fog.enabled = false
      if (viewer.scene.sun) viewer.scene.sun.show = false
      if (viewer.scene.moon) viewer.scene.moon.show = false
      viewer.scene.backgroundColor = new Cesium.Color(0, 0.02, 0.05, 1.0)

      // Default camera: pull back to see the whole Earth
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 20, 25_000_000),
      })

      // Bloom post-processing
      try {
        const bloom = viewer.scene.postProcessStages.bloom
        bloom.enabled = true
        bloom.uniforms['glowOnly'] = false
        bloom.uniforms['contrast'] = 128
        bloom.uniforms['brightness'] = -0.3
        bloom.uniforms['delta'] = 1.0
        bloom.uniforms['sigma'] = 3.78
        bloom.uniforms['stepSize'] = 5.0
      } catch {
        // bloom not supported — skip silently
      }

      viewerRef.current = viewer

      if (!continentsLoadedRef.current) {
        continentsLoadedRef.current = true
        const outlineColor = new Cesium.Color(0.0, 0.85, 1.0, 0.7)
        const fillColor = new Cesium.Color(0.0, 0.85, 1.0, 0.02)
        Cesium.GeoJsonDataSource.load('/geo/ne_110m_land.geojson', {
          clampToGround: false,
          stroke: outlineColor,
          strokeWidth: 1,
          fill: fillColor,
        }).then((dataSource) => {
          const liveViewer = viewerRef.current
          if (!liveViewer || liveViewer.isDestroyed()) return

          continentsRef.current = dataSource
          liveViewer.dataSources.add(dataSource)
          dataSource.show = showContinents

          for (const entity of dataSource.entities.values) {
            if (entity.polygon) {
              entity.polygon.outline = new Cesium.ConstantProperty(true)
              entity.polygon.outlineColor = new Cesium.ConstantProperty(outlineColor)
              entity.polygon.material = new Cesium.ColorMaterialProperty(fillColor)
              entity.polygon.fill = new Cesium.ConstantProperty(true)
              entity.polygon.height = new Cesium.ConstantProperty(1000)
            }
            if (entity.label) {
              entity.label.show = new Cesium.ConstantProperty(false)
            }
          }
        }).catch((err) => {
          console.warn('Continents overlay load failed:', err)
        })
      }
    } catch (err) {
      console.error('Cesium Viewer init failed:', err)
    }

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
      }
      initializedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (continentsRef.current) {
      continentsRef.current.show = showContinents
    }
  }, [showContinents])

  // Build point cloud when snapshot loads
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot) return

    // Remove previous collection
    if (pointCollectionRef.current) {
      viewer.scene.primitives.remove(pointCollectionRef.current)
    }

    const points = new Cesium.PointPrimitiveCollection()
    viewer.scene.primitives.add(points)
    pointCollectionRef.current = points

    const noradMap = new Map<number, number>()
    snapshot.objects.forEach((obj, i) => noradMap.set(obj.norad_id, i))
    noradIndexMapRef.current = noradMap

    const safeIdx = Math.min(Math.max(timeIndex, 0), snapshot.times_utc.length - 1)
    const prims = snapshot.objects.map((obj) => {
      const pos = obj.positions_ecef_m[safeIdx] ?? obj.positions_ecef_m[0]
      return points.add({
        position: new Cesium.Cartesian3(pos[0], pos[1], pos[2]),
        color: obj.source_group === 'ACTIVE'
          ? new Cesium.Color(0, 1, 1, 0.9)        // cyan
          : new Cesium.Color(1, 0.2, 0.6, 0.8),   // neon pink
        pixelSize: 3,
        scaleByDistance: new Cesium.NearFarScalar(1.5e6, 4.0, 5.5e7, 1.0),
      })
    })
    pointPrimsRef.current = prims
  }, [snapshot]) // eslint-disable-line react-hooks/exhaustive-deps

  // Update positions on timeIndex change
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot || pointPrimsRef.current.length === 0) return

    const safeIdx = Math.min(Math.max(timeIndex, 0), snapshot.times_utc.length - 1)
    snapshot.objects.forEach((obj, i) => {
      const pos = obj.positions_ecef_m[safeIdx]
      if (pos && pointPrimsRef.current[i]) {
        pointPrimsRef.current[i].position = new Cesium.Cartesian3(pos[0], pos[1], pos[2])
      }
    })
    viewer.scene.requestRender()
  }, [timeIndex, snapshot])

  // Handle selected event
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot || !selectedEvent) return

    const noradMap = noradIndexMapRef.current
    const prims = pointPrimsRef.current

    // Jump to TCA timestep
    onTimeChange(selectedEvent.tca_index_snapshot)
    const tIdx = selectedEvent.tca_index_snapshot

    // Reset all points
    prims.forEach((p) => {
      p.color = p.color.withAlpha(0.4)
      p.pixelSize = 2.0
    })

    const primaryIdx = noradMap.get(selectedEvent.primary_norad_id)
    const secondaryIdx = noradMap.get(selectedEvent.secondary_norad_id)

    if (primaryIdx !== undefined && prims[primaryIdx]) {
      prims[primaryIdx].color = new Cesium.Color(1, 0.3, 0, 1)
      prims[primaryIdx].pixelSize = 10
    }
    if (secondaryIdx !== undefined && prims[secondaryIdx]) {
      prims[secondaryIdx].color = new Cesium.Color(1, 0, 0, 1)
      prims[secondaryIdx].pixelSize = 10
    }

    // Remove previous pulse entity
    if (pulseEntityRef.current) {
      viewer.entities.remove(pulseEntityRef.current)
      pulseEntityRef.current = null
    }

    if (primaryIdx !== undefined && secondaryIdx !== undefined) {
      const pPos = snapshot.objects[primaryIdx].positions_ecef_m[tIdx]
      const sPos = snapshot.objects[secondaryIdx].positions_ecef_m[tIdx]

      if (pPos && sPos) {
        const primaryCart = new Cesium.Cartesian3(pPos[0], pPos[1], pPos[2])
        const secondaryCart = new Cesium.Cartesian3(sPos[0], sPos[1], sPos[2])

        pulseEntityRef.current = viewer.entities.add({
          polyline: {
            positions: [primaryCart, secondaryCart],
            width: 3,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.4,
              color: new Cesium.CallbackProperty(() => {
                const alpha = 0.4 + 0.6 * Math.abs(Math.sin(Date.now() / 400))
                return new Cesium.Color(1, 0, 0, alpha)
              }, false),
            }),
          },
        })

        // Camera fly-to midpoint, 2000 km above
        const mid = Cesium.Cartesian3.midpoint(primaryCart, secondaryCart, new Cesium.Cartesian3())
        const midCarto = Cesium.Cartographic.fromCartesian(mid)
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromRadians(
            midCarto.longitude,
            midCarto.latitude,
            midCarto.height + 2_000_000
          ),
          duration: 2.0,
          easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
        })
      }
    }

    viewer.scene.requestRender()
  }, [selectedEvent]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#00050d' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {!snapshot && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(0,200,255,0.4)', fontSize: 12, letterSpacing: '0.1em',
          pointerEvents: 'none',
        }}>
          LOADING ORBIT DATA...
        </div>
      )}
    </div>
  )
}
